import pytest

from score_to_song import abc
from score_to_song.abc import Event, Pitch


def test_pitch_names_and_midi():
    assert abc.parse_pitch("C4").midi == 60
    assert abc.parse_pitch("Bb4").midi == 70
    assert abc.parse_pitch("C#5").midi == 73
    with pytest.raises(ValueError):
        abc.parse_pitch("H4")


def test_pack_ties_across_barline_and_splits_unsupported_lengths():
    bars = abc.pack(abc.parse_melody("D5:18 E5:2 F5:8"), 16)
    assert [[(e.units, e.tie) for e in bar] for bar in bars] == [[(16, True)], [(2, False), (2, False), (8, False), (4, False)]]
    assert abc.bar_text(bars[0], "Dm") == "=d16-"
    # 10 units is not a native length: 8 + 2, tied
    assert abc.bar_text(abc.pack(abc.parse_melody("A4:10 r:6"), 16)[0], "C") == "=A8-=A2z6"


def test_bar_check():
    with pytest.raises(ValueError):
        abc.parse_melody("A4:8 | A4:8", 16)
    assert len(abc.parse_melody("A4:16 | A4:16", 16)) == 2


def test_naturals_when_needed_follow_signature_and_bar_state():
    bar = [Event(Pitch("B", -1, 4), 4), Event(Pitch("B", 0, 4), 4), Event(Pitch("E", 0, 5), 4), Event(Pitch("F", 1, 4), 2), Event(Pitch("F", 0, 5), 2)]
    # Dm: B is flat by signature; after ^F, f needs '=' (accidentals apply to the letter in every octave)
    assert abc.bar_text(bar, "Dm", "when-needed") == "_B4=B4e4^F2=f2"
    assert abc.bar_text(bar, "Dm", "always") == "_B4=B4=e4^F2=f2"


def test_parse_bar_reads_back_what_is_written():
    chord, events = abc.parse_bar('"Gm/D"d8_e2d2^c4-', "Dm", 16)
    assert chord == "Gm/D"
    assert [(e.pitch.midi, e.units, e.tie) for e in events] == [(74, 8, False), (75, 2, False), (74, 2, False), (73, 4, True)]
    # unmarked B in D minor is B flat
    assert abc.parse_bar('"Dm"B16', "Dm", 16)[1][0].pitch.midi == 70


def test_chords_and_generated_accompaniment():
    assert abc.parse_chord("Eb/D") == (3, (0, 4, 7), 2)
    assert abc.bar_text(abc.accompaniment_bar("Dm", "ostinato", 16), "Dm", "when-needed") == "D,6A,6D4"
    assert abc.bar_text(abc.accompaniment_bar("Dm", "drone", 16), "Dm", "when-needed") == "D,16"
    with pytest.raises(ValueError):
        abc.parse_chord("Cmaj9")


def test_ties_must_join_equal_pitches():
    with pytest.raises(ValueError):
        abc.check_ties(abc.pack(abc.parse_melody("A4:8~ B4:8"), 16))
