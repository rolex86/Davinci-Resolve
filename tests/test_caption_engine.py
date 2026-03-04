from kinetic_captions.caption_engine import (
    CaptionData,
    CaptionSettings,
    MODE_COMBO,
    MODE_HIGHLIGHT,
    MODE_REVEAL,
    WINDOW_CENTERED,
    WINDOW_TRAILING,
    WordItem,
    compute_caption_state,
)


def _sample_data() -> CaptionData:
    words = (
        WordItem(0, "Ahoj", 0.1, 0.4),
        WordItem(1, "tohle", 0.5, 0.8),
        WordItem(2, "je", 0.9, 1.1),
        WordItem(3, "test.", 1.2, 1.5),
    )
    return CaptionData(words=words, text="Ahoj tohle je test.")


def test_reveal_mode_shows_only_revealed_words() -> None:
    state = compute_caption_state(
        _sample_data(), 0.95, CaptionSettings(mode=MODE_REVEAL, rolling_window=False)
    )
    assert state.display_text == "Ahoj tohle je"
    assert state.highlighted_word == ""


def test_highlight_mode_shows_full_text() -> None:
    state = compute_caption_state(
        _sample_data(), 0.95, CaptionSettings(mode=MODE_HIGHLIGHT, rolling_window=False)
    )
    assert state.display_text == "Ahoj tohle je test."
    assert state.highlighted_word == "je"


def test_combo_mode_with_trailing_window() -> None:
    state = compute_caption_state(
        _sample_data(),
        1.25,
        CaptionSettings(
            mode=MODE_COMBO,
            rolling_window=True,
            window_words=2,
            window_mode=WINDOW_TRAILING,
        ),
    )
    assert state.display_text == "je test."
    assert state.highlighted_word == "test."


def test_combo_mode_with_centered_window() -> None:
    state = compute_caption_state(
        _sample_data(),
        0.95,
        CaptionSettings(
            mode=MODE_COMBO,
            rolling_window=True,
            window_words=3,
            window_mode=WINDOW_CENTERED,
        ),
    )
    assert "tohle" in state.display_text
    assert state.highlighted_word == "je"
