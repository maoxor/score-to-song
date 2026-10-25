"""Render YuE2 requests with mlx-Yue (local, offline), one at a time, with a provenance file per run.

Each request goes through the port's own helper (skills/yue2-music/scripts/generate_music.py), which saves
the effective request, timings and native artifacts (audio.flac, score.abc, semantic tokens, noise) in
<out>/<request id>/. A run whose directory already exists is skipped, never repeated blindly or overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from .util import WEIGHTS, git_commit, now_utc, rel, sha256_file, tool_info, write_json, yue_dir


def render(requests: list[Path], out_root: Path, engines: Path, profile: str = "reference", precision: str = "bf16",
           allow_battery: bool = False) -> list[dict]:
    yue = yue_dir(engines)
    python = yue / ".venv/bin/python"
    helper = yue / "skills/yue2-music/scripts/generate_music.py"
    for p in (python, helper, yue / "models/paths.json"):
        if not p.exists():
            raise SystemExit(f"missing {p}; run scripts/install.sh or set --engines (see docs/install.md)")
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    commit = git_commit(yue)
    env = dict(os.environ, MLX_ENABLE_TF32="0")
    results = []
    for req_path in requests:
        req_path = req_path.resolve()
        req = json.loads(req_path.read_text(encoding="utf-8"))
        run_dir = out_root / req["id"]
        abc_file = req_path.parent / req["abc_path"] if req.get("abc_path") else None
        if run_dir.exists():
            old_file = out_root / f"{req['id']}.json"
            old = json.loads(old_file.read_text()) if old_file.exists() else None
            same = old is not None and old["request"] == req and \
                old["abc_sha256"] == (sha256_file(abc_file) if abc_file else None)
            if not same:
                raise SystemExit(f"{req['id']}: {rel(run_dir)} exists but was rendered from a different request or score. "
                                 "Change the seed or the id, or move that folder away; renders are never replaced.")
            if old["returncode"] != 0 or not old["outputs"]:
                raise SystemExit(f"{req['id']}: the earlier render in {rel(run_dir)} failed (log: {rel(old_file.with_suffix('.log'))}). "
                                 "It is kept for diagnosis; move that folder and its .json/.log away to render again.")
            print(f"{req['id']}: {rel(run_dir)} already exists for this exact request, skipped", flush=True)
            continue
        cmd = [str(python), str(helper), "--request", str(req_path), "--profile", profile, "--precision", precision,
               "--output", str(run_dir), "--execute"] + (["--allow-battery"] if allow_battery else [])
        started = now_utc()
        print(f"{req['id']}: rendering (needs 10-12 GB of free memory)...", flush=True)
        proc = subprocess.run(cmd, cwd=yue, env=env, capture_output=True, text=True)
        (out_root / f"{req['id']}.log").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr)
        audio = sorted(run_dir.rglob("audio.flac"))
        meta = {"provider": "YuE2-3B via mlx-Yue (community MLX port), run locally offline, no cost",
                "tool": tool_info(),
                "runtime": {"code": "github.com/vanch007/mlx-Yue", "commit": commit, "backend": "MLX",
                            "profile": profile, "precision": precision, "allow_battery": allow_battery},
                "weights": WEIGHTS, "request_file": rel(req_path), "request": req,
                "abc_sha256": sha256_file(abc_file) if abc_file else None,
                "date_utc": started, "returncode": proc.returncode,
                "generation_id": f"local-{hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()[:16]}",
                "outputs": [{"path": rel(f), "sha256": sha256_file(f)} for f in audio], "cost_eur": 0.0}
        write_json(out_root / f"{req['id']}.json", meta)
        for f in audio:
            os.chmod(f, 0o444)
        if proc.returncode != 0 or not audio:
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
            print(f"{req['id']}: FAILED (code {proc.returncode}); log: {rel(out_root / (req['id'] + '.log'))}\n  " + "\n  ".join(tail), flush=True)
            if any("memory" in line.lower() or "swap" in line.lower() for line in tail):
                print("  hint: the port stops instead of swapping; close memory-hungry apps and retry", flush=True)
        else:
            print(json.dumps({"id": req["id"], "audio": [o["path"] for o in meta["outputs"]]}), flush=True)
        results.append(meta)
    return results
