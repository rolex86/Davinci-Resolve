-- Kinetic Captions runtime helpers for Fusion expressions.
-- Best-effort implementation for file/inline JSON loading, caching, reveal/highlight logic,
-- rolling windows, wrapping and presets.

local M = {}

local CACHE = _G.__KINETIC_CAPTIONS_CACHE
if not CACHE then
  CACHE = {
    data_by_key = {},
    state_by_key = {},
  }
  _G.__KINETIC_CAPTIONS_CACHE = CACHE
end

local MODE_REVEAL = 0
local MODE_HIGHLIGHT = 1
local MODE_COMBO = 2

local WINDOW_TRAILING = 0
local WINDOW_CENTERED = 1

local LINES_AUTO = 0
local LINES_SINGLE = 1
local LINES_DOUBLE = 2

local PRESET_REELS = 0
local PRESET_CLEAN = 1
local PRESET_MINIMAL = 2
local PRESET_CUSTOM = 3

local function get_comp(tool)
  if tool and tool.Comp then
    return tool.Comp
  end
  if comp then
    return comp
  end
  if fu and fu.GetCurrentComp then
    return fu:GetCurrentComp()
  end
  return nil
end

local function get_time(tool)
  local c = get_comp(tool)
  if c and c.CurrentTime then
    return tonumber(c.CurrentTime) or 0
  end
  return 0
end

local function get_fps(tool)
  local c = get_comp(tool)
  if c and c.GetPrefs then
    local ok, rate = pcall(function()
      return c:GetPrefs("Comp.FrameFormat.Rate")
    end)
    if ok and rate and tonumber(rate) and tonumber(rate) > 0 then
      return tonumber(rate)
    end
  end
  return 25
end

local function get_input(tool, name, default)
  if not tool then
    return default
  end
  local frame = get_time(tool)
  local ok, value = pcall(function()
    return tool:GetInput(name, frame)
  end)
  if not ok or value == nil then
    return default
  end
  return value
end

local function as_number(value, default)
  local n = tonumber(value)
  if n == nil then
    return default
  end
  return n
end

local function as_bool(value)
  if value == true or value == 1 or value == "1" then
    return true
  end
  if type(value) == "string" then
    local lower = string.lower(value)
    return lower == "true" or lower == "on" or lower == "yes"
  end
  return false
end

local function as_string(value)
  if value == nil then
    return ""
  end
  return tostring(value)
end

local function hash_text(text)
  local h = 0
  for i = 1, #text do
    h = (h * 131 + string.byte(text, i)) % 4294967296
  end
  return tostring(h)
end

local function read_file(path)
  local f = io.open(path, "rb")
  if not f then
    return nil, "Missing words.json"
  end
  local content = f:read("*a")
  f:close()
  if not content or content == "" then
    return nil, "Empty words.json"
  end
  return content, nil
end

local json = {}

local function decode_error(str, idx, msg)
  error(string.format("Invalid JSON at position %d: %s", idx, msg))
end

local function skip_whitespace(str, idx)
  local _, e = string.find(str, "^[ \n\r\t]+", idx)
  if e then
    idx = e + 1
  end
  return idx
end

local function parse_string(str, i)
  local res = ""
  i = i + 1
  local j = i
  while j <= #str do
    local c = string.sub(str, j, j)
    if c == '"' then
      res = res .. string.sub(str, i, j - 1)
      return res, j + 1
    elseif c == "\\" then
      res = res .. string.sub(str, i, j - 1)
      local esc = string.sub(str, j + 1, j + 1)
      if esc == "\"" or esc == "\\" or esc == "/" then
        res = res .. esc
      elseif esc == "b" then
        res = res .. "\b"
      elseif esc == "f" then
        res = res .. "\f"
      elseif esc == "n" then
        res = res .. "\n"
      elseif esc == "r" then
        res = res .. "\r"
      elseif esc == "t" then
        res = res .. "\t"
      else
        decode_error(str, j, "invalid escape char")
      end
      j = j + 2
      i = j
    else
      j = j + 1
    end
  end
  decode_error(str, i, "unterminated string")
end

local function parse_number(str, i)
  local x = string.find(str, "^-?%d+%.?%d*[eE]?[+%-]?%d*", i)
  if not x then
    decode_error(str, i, "invalid number")
  end
  local s, e = string.find(str, "^-?%d+%.?%d*[eE]?[+%-]?%d*", i)
  local n = tonumber(string.sub(str, s, e))
  if not n then
    decode_error(str, i, "invalid number")
  end
  return n, e + 1
end

local parse_value

local function parse_array(str, i)
  i = i + 1
  local res = {}
  i = skip_whitespace(str, i)
  if string.sub(str, i, i) == "]" then
    return res, i + 1
  end
  while true do
    local val
    val, i = parse_value(str, i)
    res[#res + 1] = val
    i = skip_whitespace(str, i)
    local c = string.sub(str, i, i)
    if c == "]" then
      return res, i + 1
    elseif c ~= "," then
      decode_error(str, i, "expected ']' or ','")
    end
    i = skip_whitespace(str, i + 1)
  end
end

local function parse_object(str, i)
  i = i + 1
  local res = {}
  i = skip_whitespace(str, i)
  if string.sub(str, i, i) == "}" then
    return res, i + 1
  end
  while true do
    if string.sub(str, i, i) ~= '"' then
      decode_error(str, i, "expected string key")
    end
    local key
    key, i = parse_string(str, i)
    i = skip_whitespace(str, i)
    if string.sub(str, i, i) ~= ":" then
      decode_error(str, i, "expected ':'")
    end
    i = skip_whitespace(str, i + 1)
    local val
    val, i = parse_value(str, i)
    res[key] = val
    i = skip_whitespace(str, i)
    local c = string.sub(str, i, i)
    if c == "}" then
      return res, i + 1
    elseif c ~= "," then
      decode_error(str, i, "expected '}' or ','")
    end
    i = skip_whitespace(str, i + 1)
  end
end

parse_value = function(str, i)
  i = skip_whitespace(str, i)
  local c = string.sub(str, i, i)
  if c == '"' then
    return parse_string(str, i)
  elseif c == "{" then
    return parse_object(str, i)
  elseif c == "[" then
    return parse_array(str, i)
  elseif c == "-" or c:match("%d") then
    return parse_number(str, i)
  elseif string.sub(str, i, i + 3) == "true" then
    return true, i + 4
  elseif string.sub(str, i, i + 4) == "false" then
    return false, i + 5
  elseif string.sub(str, i, i + 3) == "null" then
    return nil, i + 4
  else
    decode_error(str, i, "unexpected character")
  end
end

function json.decode(str)
  if type(str) ~= "string" then
    error("expected string for JSON decode")
  end
  local res, idx = parse_value(str, 1)
  idx = skip_whitespace(str, idx)
  if idx <= #str then
    decode_error(str, idx, "trailing garbage")
  end
  return res
end

local function sanitize_words(raw_words)
  if type(raw_words) ~= "table" then
    return nil, "Invalid JSON: words array missing"
  end
  local words = {}
  for i, item in ipairs(raw_words) do
    if type(item) == "table" then
      local w = as_string(item.w)
      local s = as_number(item.s, -1)
      local e = as_number(item.e, -1)
      if w ~= "" and s >= 0 and e > s then
        words[#words + 1] = {
          i = as_number(item.i, i - 1),
          w = w,
          s = s,
          e = e,
        }
      end
    end
  end
  if #words == 0 then
    return nil, "Invalid JSON: no valid words"
  end
  table.sort(words, function(a, b)
    if a.s == b.s then
      return a.i < b.i
    end
    return a.s < b.s
  end)
  return words, nil
end

local function parse_payload(raw)
  local ok, payload = pcall(json.decode, raw)
  if not ok then
    return nil, "Invalid JSON"
  end
  local words, err = sanitize_words(payload.words)
  if not words then
    return nil, err
  end
  return {
    words = words,
    text = as_string(payload.text),
    layout_hints = payload.layout_hints or {},
  }, nil
end

local function source_key(tool)
  local mode = as_number(get_input(tool, "DataMode", 0), 0)
  local file_path = as_string(get_input(tool, "DataSource", ""))
  local inline_json = as_string(get_input(tool, "InlineJson", ""))
  if mode == 1 then
    return "inline:" .. hash_text(inline_json), mode, inline_json
  end
  return "file:" .. file_path, mode, file_path
end

local function load_data(tool)
  local frame = get_time(tool)
  local key, mode, source = source_key(tool)
  local cache = CACHE.data_by_key[key]

  if mode == 1 then
    if cache then
      return cache
    end
    if source == "" then
      return { ok = false, error = "Missing inline JSON", words = {} }
    end
    local parsed, err = parse_payload(source)
    local data = { ok = parsed ~= nil, error = err, words = parsed and parsed.words or {}, parsed = parsed }
    CACHE.data_by_key[key] = data
    return data
  end

  local probe_every = 15
  local should_probe = (not cache) or (not cache.last_probe) or ((frame - cache.last_probe) >= probe_every)
  if cache and not should_probe then
    return cache
  end

  if source == "" then
    local missing = { ok = false, error = "Missing words.json", words = {}, last_probe = frame }
    CACHE.data_by_key[key] = missing
    return missing
  end

  local raw, read_err = read_file(source)
  if not raw then
    local missing = { ok = false, error = read_err or "Missing words.json", words = {}, last_probe = frame }
    CACHE.data_by_key[key] = missing
    return missing
  end

  local raw_hash = hash_text(raw)
  if cache and cache.raw_hash == raw_hash then
    cache.last_probe = frame
    return cache
  end

  local parsed, err = parse_payload(raw)
  local data = {
    ok = parsed ~= nil,
    error = err,
    words = parsed and parsed.words or {},
    parsed = parsed,
    raw_hash = raw_hash,
    last_probe = frame,
  }
  CACHE.data_by_key[key] = data
  return data
end

local function find_reveal_index(words, t)
  local idx = -1
  for i = 1, #words do
    if words[i].s <= t then
      idx = i - 1
    else
      break
    end
  end
  return idx
end

local function find_highlight_index(words, t, lead, lag)
  local left = t + lead
  local right = t - lag
  for i = 1, #words do
    local item = words[i]
    if item.s <= left and right < item.e then
      return i - 1
    end
  end
  return find_reveal_index(words, left)
end

local function make_window(total, current, visible_end, rolling, window_words, window_mode)
  if visible_end < 0 then
    return 0, -1
  end
  if not rolling then
    return 0, visible_end
  end

  local start_idx
  local end_idx
  if window_mode == WINDOW_CENTERED then
    local half = math.floor(window_words / 2)
    start_idx = math.max(0, current - half)
    end_idx = start_idx + window_words - 1
    if end_idx > visible_end then
      end_idx = visible_end
      start_idx = math.max(0, end_idx - window_words + 1)
    end
  else
    end_idx = visible_end
    start_idx = math.max(0, end_idx - window_words + 1)
  end

  end_idx = math.min(end_idx, total - 1)
  return start_idx, end_idx
end

local function wrap_words(tokens, max_chars, max_words)
  local lines = { {} }
  for _, token in ipairs(tokens) do
    local line = lines[#lines]
    local candidate = table.concat(line, " ")
    if candidate ~= "" then
      candidate = candidate .. " " .. token
    else
      candidate = token
    end
    if #line > 0 and (#candidate > max_chars or #line >= max_words) then
      lines[#lines + 1] = { token }
    else
      line[#line + 1] = token
    end
  end

  local rendered = {}
  for _, line in ipairs(lines) do
    if #line > 0 then
      rendered[#rendered + 1] = table.concat(line, " ")
    end
  end
  return rendered
end

local function render_lines(tokens, lines_mode, max_chars, max_words)
  if #tokens == 0 then
    return ""
  end
  if lines_mode == LINES_SINGLE then
    return table.concat(tokens, " ")
  end

  local wrapped = wrap_words(tokens, max_chars, max_words)
  if lines_mode == LINES_DOUBLE and #wrapped > 2 then
    local second = {}
    for i = 2, #wrapped do
      second[#second + 1] = wrapped[i]
    end
    wrapped = { wrapped[1], table.concat(second, " ") }
  end
  return table.concat(wrapped, "\n")
end

local function preset_number(preset, custom, reels, clean, minimal)
  if preset == PRESET_CUSTOM then
    return custom
  elseif preset == PRESET_REELS then
    return reels
  elseif preset == PRESET_CLEAN then
    return clean
  elseif preset == PRESET_MINIMAL then
    return minimal
  end
  return custom
end

local function compute_state(tool)
  local key = tostring(tool) .. ":" .. tostring(get_time(tool))
  local cached = CACHE.state_by_key[key]
  if cached then
    return cached
  end

  local data = load_data(tool)
  local state = {
    base_text = "",
    highlight_word = "",
    error = "",
    mode = as_number(get_input(tool, "Mode", 0), 0),
    highlight_index = -1,
    has_highlight = false,
  }

  if not data.ok then
    state.base_text = as_string(data.error ~= "" and data.error or "Invalid JSON")
    state.error = state.base_text
    CACHE.state_by_key[key] = state
    return state
  end

  local words = data.words
  local fps = get_fps(tool)
  local t = (get_time(tool) / fps) + as_number(get_input(tool, "TimingOffset", 0), 0)
  local lead = as_number(get_input(tool, "LeadSec", 0), 0)
  local lag = as_number(get_input(tool, "LagSec", 0), 0)

  local reveal_index = find_reveal_index(words, t + lead)
  local highlight_index = find_highlight_index(words, t, lead, lag)
  if highlight_index < 0 then
    highlight_index = reveal_index
  end

  local mode = as_number(get_input(tool, "Mode", MODE_REVEAL), MODE_REVEAL)
  local visible_end = (#words - 1)
  if mode ~= MODE_HIGHLIGHT then
    visible_end = reveal_index
  end

  local rolling = as_bool(get_input(tool, "RollingWindow", 1))
  local window_words = math.max(1, math.floor(as_number(get_input(tool, "WindowWords", 10), 10)))
  local window_mode = math.floor(as_number(get_input(tool, "WindowMode", WINDOW_TRAILING), WINDOW_TRAILING))

  local current = highlight_index
  if current < 0 then
    current = visible_end
  end

  local start_idx, end_idx = make_window(#words, current, visible_end, rolling, window_words, window_mode)

  local tokens = {}
  for i = start_idx + 1, end_idx + 1 do
    if words[i] then
      tokens[#tokens + 1] = words[i].w
    end
  end

  local max_chars = math.max(4, math.floor(as_number(get_input(tool, "MaxLineChars", 32), 32)))
  local max_words_per_line = math.max(1, math.floor(as_number(get_input(tool, "MaxWordsPerLine", 7), 7)))
  local lines_mode = math.floor(as_number(get_input(tool, "LinesMode", LINES_AUTO), LINES_AUTO))

  state.base_text = render_lines(tokens, lines_mode, max_chars, max_words_per_line)
  if mode == MODE_HIGHLIGHT or mode == MODE_COMBO then
    if highlight_index >= 0 and words[highlight_index + 1] then
      state.highlight_word = words[highlight_index + 1].w
      state.has_highlight = true
      state.highlight_index = highlight_index
    end
  end

  if state.base_text == "" then
    if mode == MODE_HIGHLIGHT then
      state.base_text = ""
    else
      state.base_text = ""
    end
  end

  CACHE.state_by_key[key] = state
  return state
end

function M.base_text(tool)
  local state = compute_state(tool)
  return state.base_text
end

function M.highlight_word(tool)
  local state = compute_state(tool)
  return state.highlight_word
end

function M.highlight_visible(tool)
  local state = compute_state(tool)
  if state.has_highlight then
    return 1
  end
  return 0
end

function M.font_size(tool)
  local preset = math.floor(as_number(get_input(tool, "Preset", PRESET_REELS), PRESET_REELS))
  local custom = as_number(get_input(tool, "FontSize", 0.07), 0.07)
  return preset_number(preset, custom, 0.085, 0.072, 0.062)
end

function M.tracking(tool)
  local preset = math.floor(as_number(get_input(tool, "Preset", PRESET_REELS), PRESET_REELS))
  local custom = as_number(get_input(tool, "Tracking", 1), 1)
  return preset_number(preset, custom, 1.1, 1.0, 0.8)
end

function M.outline_width(tool)
  local preset = math.floor(as_number(get_input(tool, "Preset", PRESET_REELS), PRESET_REELS))
  local custom = as_number(get_input(tool, "OutlineWidth", 0.02), 0.02)
  return preset_number(preset, custom, 0.03, 0.02, 0.0)
end

function M.shadow_blur(tool)
  local preset = math.floor(as_number(get_input(tool, "Preset", PRESET_REELS), PRESET_REELS))
  local custom = as_number(get_input(tool, "ShadowBlur", 0.02), 0.02)
  return preset_number(preset, custom, 0.025, 0.018, 0.0)
end

return M
