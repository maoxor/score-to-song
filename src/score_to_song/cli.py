"""Command line: score-to-song <command>. Each command does one step of the workflow (docs/workflow.md)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .util import engines_dir


def _engines(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--engines", help="directory holding mlx-Yue/ and models/separation/ "
                                          "(default: $SCORE_TO_SONG_ENGINES, else ./vendor)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="score-to-song", description="Write a melody as a score, have YuE2 sing it "
                                 "locally (mlx-Yue on Apple Silicon), extend it, layer voices, mix with linear gains.")
    ap.add_argument("--version", action="version", version=f"score-to-song {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check tools, engines, weights and free memory (read-only)")
    _engines(p)
    p.add_argument("--hash", action="store_true", help="also verify the separation model's SHA-256")

    p = sub.add_parser("compose", help="score file (.toml) -> native YuE2 ABC + one request per seed")
    p.add_argument("scores", nargs="+", type=Path)
    p.add_argument("--out", type=Path, required=True, help="folder for the .abc and req_*.json files")
    p.add_argument("--force", action="store_true", help="replace files whose content changed")

    p = sub.add_parser("import-abc", help="native ABC (+ request) -> editable score file; checked by round trip")
    p.add_argument("abc", type=Path)
    p.add_argument("--request", type=Path, help="request JSON giving style, lyrics and seed")
    p.add_argument("--out", type=Path, required=True, help="new .toml file")
    p.add_argument("--id", help="score id (default: from the request id)")

    p = sub.add_parser("render", help="render requests with YuE2 (one at a time, never overwrites)")
    p.add_argument("requests", nargs="+", type=Path)
    p.add_argument("--out", type=Path, required=True, help="folder receiving one sub-folder per request id")
    p.add_argument("--profile", default="reference", choices=["fast", "standard", "reference"],
                   help="mlx-Yue preset: fast = 8 diffusion steps (audition), standard/reference = 32 (default: reference)")
    p.add_argument("--precision", default="bf16")
    p.add_argument("--allow-battery", action="store_true", help="the port refuses to run on battery unless allowed")
    _engines(p)

    p = sub.add_parser("continue", help="keep a render up to --keep-s and let YuE2 sing the rest of a new score")
    p.add_argument("--source", type=Path, required=True, help="source render folder")
    p.add_argument("--keep-s", type=float, required=True, help="seconds of the source kept as they are")
    p.add_argument("--request", type=Path, required=True, help="request of the new score (repeats the source up to keep-s)")
    p.add_argument("--out", type=Path, required=True, help="new render folder")
    p.add_argument("--no-score-check", action="store_true", help="skip the check that both scores agree before keep-s")
    p.add_argument("--memory-budget-gib", type=float, default=16, help="mlx-Yue memory guard (default 16; it stops instead of swapping)")
    _engines(p)

    p = sub.add_parser("separate", help="estimate the voice of renders (BS-RoFormer), 48 kHz float WAV")
    p.add_argument("inputs", nargs="+", type=Path, help="render folders or audio files")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--name", action="append", help="output name per input (default: folder or file name)")
    p.add_argument("--keep-accompaniment", action="store_true", help="also keep the accompaniment estimate")
    p.add_argument("--suffix", default="_voice_estimate", help="appended to the output name (default: _voice_estimate)")
    _engines(p)

    p = sub.add_parser("mix", help="mix from a recipe (.toml): main track, layers, gains, loop test")
    p.add_argument("recipe", type=Path)
    p.add_argument("--out", type=Path, help="output WAV (default: the recipe's 'output')")
    p.add_argument("--path", action="append", default=[], metavar="NAME=DIR", help="set a {NAME} path variable of the recipe")

    p = sub.add_parser("listen", help="loudness-matched copies (linear gain) + a local HTML page")
    p.add_argument("items", nargs="+", help="file.wav, file.wav@START-END or Label=file.wav@START-END")
    p.add_argument("--out", type=Path, required=True, help="new folder")
    p.add_argument("--target", type=float, default=-20.0, help="LUFS (default -20)")
    p.add_argument("--title", default="Listening")

    a = ap.parse_args(argv)
    try:
        if a.command == "doctor":
            from .doctor import doctor
            return doctor(engines_dir(a.engines), a.hash)
        if a.command == "compose":
            from .compose import compose
            for s in a.scores:
                print(json.dumps(compose(s, a.out, a.force), ensure_ascii=False))
        elif a.command == "import-abc":
            from .importer import import_files
            print(json.dumps(import_files(a.abc, a.request, a.out, a.id), ensure_ascii=False))
        elif a.command == "render":
            from .render import render
            results = render(a.requests, a.out, engines_dir(a.engines), a.profile, a.precision, a.allow_battery)
            return 1 if any(r["returncode"] != 0 or not r["outputs"] for r in results) else 0
        elif a.command == "continue":
            from .continuation import continue_render
            meta = continue_render(a.source, a.keep_s, a.request, a.out, engines_dir(a.engines), not a.no_score_check, a.memory_budget_gib)
            print(json.dumps({k: meta[k] for k in ("kept_tokens", "generated_tokens", "truncated", "output")}, ensure_ascii=False))
        elif a.command == "separate":
            from .separate import separate
            separate(a.inputs, a.out, engines_dir(a.engines), a.name, a.keep_accompaniment, a.suffix)
        elif a.command == "mix":
            from .mix import mix
            overrides = dict(item.split("=", 1) for item in a.path)
            r = mix(a.recipe, a.out, overrides)
            print(json.dumps({"output": r["output"], "peak": r["peak"], "length_s": r["length_s"],
                              "check": r.get("check"), "loop_test": r.get("loop_test", {}).get("path")}, ensure_ascii=False))
        elif a.command == "listen":
            from .listen import build, parse_item
            r = build([parse_item(i) for i in a.items], a.out, a.target, title=a.title)
            print(f"open {a.out / 'index.html'}  ({len(r['items'])} files at {r['effective_lufs']} LUFS)")
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"error: {e.cmd[0]} failed (code {e.returncode}): {' '.join(map(str, e.cmd))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
