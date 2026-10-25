"""Continue a render: keep its sung material up to --keep-s and let YuE2 sing the rest of a new score.

Before running, the new score is checked against the source's score: every bar that starts before keep_s
must be identical in both voices (chords included), otherwise the kept tokens and the new score disagree.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

from . import abc
from .util import now_utc, rel, tool_info, yue_dir

ENGINE = Path(__file__).with_name("yue_continue_engine.py")


def check_score_prefix(source_abc: str, new_abc: str, keep_s: float) -> dict:
    bar_s = abc.bar_seconds(source_abc)
    if abs(abc.bar_seconds(new_abc) - bar_s) > 1e-9:
        raise ValueError("source and new score have different tempo or meter")
    n = math.ceil(keep_s / bar_s - 1e-9)
    src, new = abc.bars_by_voice(source_abc), abc.bars_by_voice(new_abc)
    available = min(len(src["Vocal"]), n)
    for voice in ("Vocal", "Ins"):
        for i in range(available):
            if i >= len(new[voice]) or src[voice][i] != new[voice][i]:
                got = new[voice][i] if i < len(new[voice]) else "(missing)"
                raise ValueError(f"bar {i + 1} of {voice} differs before keep_s={keep_s} s (bar {n} ends the kept part): "
                                 f"source {src[voice][i]!r}, new {got!r}")
    return {"bars_checked": available, "bars_kept": n, "bar_seconds": round(bar_s, 4),
            "source_shorter_than_kept_part": available < n}


def continue_render(source: Path, keep_s: float, request: Path, output: Path, engines: Path,
                    check: bool = True, memory_budget_gib: float = 16) -> dict:
    yue = yue_dir(engines)
    python = yue / ".venv/bin/python"
    if not python.exists():
        raise SystemExit(f"missing {python}; run scripts/install.sh or set --engines")
    source, request, output = source.resolve(), request.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"{rel(output)} exists and is not empty; nothing is overwritten")
    record = {"source": rel(source), "request_file": rel(request), "output_dir": rel(output), "tool": tool_info(),
              "started_utc": now_utc()}
    if check:
        src_req = json.loads((source / "generate/request.json").read_text(encoding="utf-8"))
        req = json.loads(request.read_text(encoding="utf-8"))
        new_abc = (request.parent / req["abc_path"]).read_text(encoding="utf-8")
        try:
            record["score_check"] = check_score_prefix(src_req["abc"], new_abc, keep_s)
        except ValueError as e:
            raise SystemExit(f"score check failed: {e}\n(use --no-score-check only if the difference is intended)") from None
    cmd = [str(python), str(ENGINE), "--source", str(source), "--keep-s", repr(keep_s), "--request", str(request),
           "--output", str(output), "--memory-budget-gib", repr(memory_budget_gib), "--record", json.dumps(record)]
    print(f"continuing {rel(source)} from {keep_s} s into {rel(output)} (10-12 GB of free memory)...", flush=True)
    proc = subprocess.run(cmd, cwd=yue, env=dict(os.environ, MLX_ENABLE_TF32="0"))
    if proc.returncode != 0:
        raise SystemExit(f"continuation failed (code {proc.returncode}); resource log: {rel(output)}.resources.json")
    meta = json.loads((output / "continuation.json").read_text())
    meta["output"]["path"] = rel(Path(meta["output"]["path"]))   # recorded as the caller sees it
    (output / "continuation.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    return meta
