import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from score_to_song import __version__
from score_to_song.cli import main
from score_to_song.listen import build, parse_item
from score_to_song.mix import loudness
from score_to_song.render import render
from score_to_song.separate import same_input
from score_to_song.util import sha256_file, tool_info

SR = 48000
SCORE = '''
id = "cli"
tempo = 60
key = "Am"
seeds = [3]
style = "Soft female voice, solo cello"

[[sections]]
name = "verse"
chords = ["Am", "Am"]
melody = "A4:16 | C5:16"
lyrics = ["Ah"]
'''


def test_version_and_compose_from_the_command_line(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0 and __version__ in capsys.readouterr().out
    (tmp_path / "cli.toml").write_text(SCORE)
    assert main(["compose", str(tmp_path / "cli.toml"), "--out", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out/req_cli_s3.json").exists()
    # an invalid score is reported as an error, not a traceback
    (tmp_path / "bad.toml").write_text(SCORE.replace("A4:16 | C5:16", "A4:16 | C5:16 | D5:16"))
    assert main(["compose", str(tmp_path / "bad.toml"), "--out", str(tmp_path / "out2")]) == 2
    assert "error:" in capsys.readouterr().err


def fake_engines(tmp_path):
    yue = tmp_path / "engines/mlx-Yue"
    for p in (".venv/bin/python", "skills/yue2-music/scripts/generate_music.py", "models/paths.json"):
        (yue / p).parent.mkdir(parents=True, exist_ok=True)
        (yue / p).write_text("")
    return tmp_path / "engines"


def test_render_never_reuses_a_failed_or_different_render(tmp_path):
    engines = fake_engines(tmp_path)
    req = {"id": "x_s1", "style": "s", "lyrics": "[Verse]", "seed": 1}
    (tmp_path / "req.json").write_text(json.dumps(req))
    out = tmp_path / "renders"
    (out / "x_s1").mkdir(parents=True)
    record = {"request": req, "abc_sha256": None, "returncode": 1, "outputs": []}
    (out / "x_s1.json").write_text(json.dumps(record))
    with pytest.raises(SystemExit, match="failed"):
        render([tmp_path / "req.json"], out, engines)
    (out / "x_s1.json").write_text(json.dumps(dict(record, request=dict(req, seed=2))))
    with pytest.raises(SystemExit, match="different request"):
        render([tmp_path / "req.json"], out, engines)
    (out / "x_s1.json").write_text(json.dumps(dict(record, returncode=0, outputs=[{"path": "a.flac"}])))
    assert render([tmp_path / "req.json"], out, engines) == []          # same request, done: skipped


def test_separation_output_is_reused_only_for_the_same_input(tmp_path):
    src, other, out = tmp_path / "a.flac", tmp_path / "b.flac", tmp_path / "a_voice_estimate.wav"
    src.write_bytes(b"render a")
    other.write_bytes(b"render b")
    out.write_bytes(b"estimate")
    assert not same_input(out, src)                                       # no sidecar: unknown origin
    (tmp_path / "a_voice_estimate.wav.json").write_text(json.dumps({"input": {"sha256": sha256_file(src)}}))
    assert same_input(out, src) and not same_input(out, other)


def test_tool_info_reports_this_checkout():
    info = tool_info()
    assert info["name"] == "score-to-song" and info["version"] == __version__
    if (Path(__file__).parents[1] / ".git").exists():                   # tests run from a Git checkout
        assert info["commit"] and len(info["commit"]) == 40


def test_listening_copies_share_one_loudness(tmp_path):
    t = np.arange(3 * SR) / SR
    quiet = 0.05 * np.sin(2 * np.pi * 220 * t)
    loud = 0.5 * np.sin(2 * np.pi * 330 * t)
    sf.write(tmp_path / "quiet.wav", np.c_[quiet, quiet], SR, subtype="FLOAT")
    sf.write(tmp_path / "loud.wav", np.c_[loud, loud], SR, subtype="FLOAT")
    assert parse_item("Main=x.wav@1-2.5") == {"path": Path("x.wav"), "label": "Main", "start": 1.0, "end": 2.5}
    items = [parse_item(f"Quiet={tmp_path / 'quiet.wav'}"), parse_item(str(tmp_path / "loud.wav"))]
    report = build(items, tmp_path / "page", target=-20.0)
    levels = [loudness(*sf.read(tmp_path / "page" / e["copy"], always_2d=True)) for e in report["items"]]
    assert abs(levels[0] - levels[1]) < 0.05 and abs(levels[0] - report["effective_lufs"]) < 0.05
    assert [e["label"] for e in report["items"]] == ["Quiet", "loud"]
    assert (tmp_path / "page/index.html").exists() and (tmp_path / "page/listening.json").exists()
    with pytest.raises(SystemExit, match="not empty"):
        build(items, tmp_path / "page")
