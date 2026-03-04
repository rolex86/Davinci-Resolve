from kinetic_captions.text_norm import RawWord, coalesce_words, compose_transcript


def test_attach_punctuation_to_previous_word() -> None:
    raw = [
        RawWord(token="Ahoj", start=0.1, end=0.2),
        RawWord(token=",", start=0.2, end=0.21),
        RawWord(token="svete", start=0.22, end=0.5),
        RawWord(token="!", start=0.5, end=0.54),
    ]
    words = coalesce_words(raw)
    assert [word["w"] for word in words] == ["Ahoj,", "svete!"]
    assert [word["i"] for word in words] == [0, 1]


def test_attach_contraction_suffix() -> None:
    raw = [
        RawWord(token="we", start=0.1, end=0.2),
        RawWord(token="'re", start=0.2, end=0.3),
        RawWord(token="testing", start=0.31, end=0.6),
    ]
    words = coalesce_words(raw)
    assert [word["w"] for word in words] == ["we're", "testing"]
    assert compose_transcript(words) == "we're testing"


def test_attach_opening_quote_to_next_word() -> None:
    raw = [
        RawWord(token="„", start=0.1, end=0.11),
        RawWord(token="Ahoj", start=0.11, end=0.2),
        RawWord(token="“", start=0.2, end=0.22),
    ]
    words = coalesce_words(raw)
    assert [word["w"] for word in words] == ["„Ahoj“"]
