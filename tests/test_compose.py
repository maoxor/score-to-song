import json
from pathlib import Path

import pytest

from score_to_song.compose import compose, load_score, lyrics_text, to_abc
from score_to_song.importer import import_files

SCORE = '''
id = "demo"
tempo = 60
key = "Am"
seeds = [7, 8]
style = "Soft female voice, solo cello"

[[sections]]
name = "intro"
chords = ["Am", "F/A"]
pattern = "drone"

[[sections]]
name = "verse"
chords = ["Am", "Dm/A", "E/A", "Am"]
melody = "A4:8 C5:8 | B4:4 C5:4 D5:8~ | D5:4 C5:4 B4:8 | A4:16"
lyrics = ["Ah", "Oh"]
'''

EXPECTED_ABC = """X:1
T:
M:4/4
L:1/16
Q:1/4=60
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:Am
% intro
V: Vocal
"Am"z16|"F/A"z16|
V: Ins
=A,,16|=A,,16|
% verse
V: Vocal
"Am"=A8=c8|"Dm/A"=B4=c4=d8-|"E/A"=d4=c4=B8|"Am"=A16|
V: Ins
=A,,6=E,6=A,4|=A,,6=A,6=D4|=A,,6=B,6=E4|=A,,6=E,6=A,4|
"""


def test_compose_writes_abc_and_one_request_per_seed(tmp_path):
    score = tmp_path / "demo.toml"
    score.write_text(SCORE)
    report = compose(score, tmp_path / "out")
    assert (tmp_path / "out/demo.abc").read_text() == EXPECTED_ABC
    req = json.loads((tmp_path / "out/req_demo_s8.json").read_text())
    assert req == {"id": "demo_s8", "style": "Soft female voice, solo cello", "lyrics": "[Intro]\n\n[Verse]\nAh\nOh",
                   "cot": "full", "seed": 8, "abc_path": "demo.abc"}
    assert report["bars"] == 6 and report["nominal_seconds"] == 24.0
    # unchanged content is accepted, changed content needs --force
    compose(score, tmp_path / "out")
    score.write_text(SCORE.replace("tempo = 60", "tempo = 62"))
    with pytest.raises(SystemExit):
        compose(score, tmp_path / "out")


def test_derived_voice_octave_lower_on_held_notes(tmp_path):
    (tmp_path / "main.toml").write_text(SCORE)
    (tmp_path / "low.toml").write_text('id = "low"\nstyle = "Warm male voice"\n\n[derive]\nfrom = "main.toml"\n'
                                        'transpose = -12\nhold_shorter_than = 6\n')
    low = load_score(tmp_path / "low.toml")
    # the tie D~D is merged, then 4-unit notes are absorbed into the sung note before them
    assert [(e.pitch.midi, e.units) for e in low.sections[1].melody] == [(57, 8), (60, 16), (62, 16), (59, 8), (57, 16)]
    assert '"Am"=A,8=C8-|"Dm/A"=C8=D8-|"E/A"=D8=B,8|"Am"=A,16|' in to_abc(low)
    assert lyrics_text(low) == "[Intro]\n\n[Verse]\nAh\nOh"
    (tmp_path / "bad.toml").write_text('[derive]\nfrom = "main.toml"\nid = "x"\n')
    with pytest.raises(ValueError, match="before the \\[derive\\] table"):
        load_score(tmp_path / "bad.toml")


def test_import_round_trip(tmp_path):
    (tmp_path / "demo.toml").write_text(SCORE)
    compose(tmp_path / "demo.toml", tmp_path / "a")
    out = import_files(tmp_path / "a/demo.abc", tmp_path / "a/req_demo_s7.json", tmp_path / "imported.toml")
    assert out["round_trip"] == "identical ABC and lyrics"
    assert to_abc(load_score(tmp_path / "imported.toml")) == EXPECTED_ABC
