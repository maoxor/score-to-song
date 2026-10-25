#!/usr/bin/env python3
"""Continuation engine, run by `score-to-song continue` with mlx-Yue's own Python, from the mlx-Yue directory.

The semantic tokens of the source render (25 per second) up to --keep-s are imposed as the start of the
song; the model then generates the rest under the new request (whose score repeats the source's score up to
that point). The acoustic stage reuses the source's initial noise for the kept frames. This keeps the vocal
identity and phrasing of the kept passage, which a fresh render of the same score does not.
Standalone on purpose: it imports only mlx-Yue and numpy. Writes native artifacts plus continuation.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np

FPS = 25


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True, help="source render directory (contains generate/semantic.npy)")
    ap.add_argument("--keep-s", type=float, required=True)
    ap.add_argument("--request", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--memory-budget-gib", type=float, default=16)
    ap.add_argument("--record", default="{}", help="JSON fields added to continuation.json (paths as the caller sees them, tool)")
    a = ap.parse_args()
    os.environ.setdefault("MLX_ENABLE_TF32", "0")
    if a.output.exists() and any(a.output.iterdir()):
        raise SystemExit("output exists and is not empty")

    from lyra.measure import ResourceMonitor
    from lyra.pipeline import SongResult, YuE2Pipeline, initial_noise
    from yue2.pipeline import SemanticResult
    from yue2.storage import identity
    from yue2.protocol import CODEC_OFFSET, GenerationConfig, resolve_sampling

    paths = json.loads(Path("models/paths.json").read_text())
    req = json.loads(a.request.read_text())
    req["abc"] = (a.request.parent / req.pop("abc_path")).read_text()
    src_tokens = np.load(a.source / "generate/semantic.npy").astype(int).tolist()
    src_noise = np.load(a.source / "generate/noise.npy")
    keep = int(round(a.keep_s * FPS))
    forced = src_tokens[:keep]

    a.output.mkdir(parents=True, exist_ok=True)
    monitor = ResourceMonitor(require_ac=False, log_path=a.output.with_name(a.output.name + ".resources.jsonl"),
                              report_path=a.output.with_name(a.output.name + ".resources.json"),
                              metadata={"command": "continue", "memory_budget_gib": a.memory_budget_gib, "precision": "bf16"})
    with monitor:
        pipe = YuE2Pipeline.from_pretrained(paths["model"], vae=paths["vae"], precision="bf16", local_files_only=True,
                                            memory_budget_gib=a.memory_budget_gib, vae_core_frames=256, progress=False,
                                            generation_config=GenerationConfig.from_dict({"ode_steps": 32}), require_ac=False)
        with pipe:
            plan = pipe.plan(**req)
            sampling = resolve_sampling(None, pipe.generation_config.semantic)
            prefix = list(plan.prefix) + [t + CODEC_OFFSET for t in forced]
            ids, timing, truncated = pipe._generate(prefix, sampling, plan.request.seed, "semantic",
                                                    negative=None, cfg_scale=1.0, legacy_off=False)
            tokens = forced + [int(t) - CODEC_OFFSET for t in ids]
            semantic = SemanticResult(plan, tokens, timing, truncated)
            noise = np.array(initial_noise(len(tokens), plan.request.seed))
            shared = min(keep, len(src_noise), len(noise))
            noise[:shared] = src_noise[:shared]
            latents = pipe.synthesize(semantic, noise=noise)
            audio = pipe.decode(latents)
            config = pipe.effective_config(plan.request)
            rid = identity({"request": plan.request.to_dict(), "config": config, "weights": pipe.weights})
            result = SongResult(audio, 48000, semantic, latents, config, pipe.weights, {"abc": plan.timing, "semantic": timing}, rid, noise)
            result.save_artifacts(a.output / "generate")
    flac = a.output / "generate/audio.flac"
    meta = {"method": "continuation: source semantic tokens imposed up to keep_s, new request generates the rest",
            "source": str(a.source), "source_semantic_sha256": hashlib.sha256(np.asarray(src_tokens, dtype=np.int32).tobytes()).hexdigest(),
            "keep_s": a.keep_s, "kept_tokens": keep, "generated_tokens": len(tokens) - keep, "truncated": truncated,
            "request_file": str(a.request), "seed": plan.request.seed, "noise": "source noise for kept frames, initial_noise(seed) after",
            "commit_mlx_yue": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "weights": paths, "memory_budget_gib": a.memory_budget_gib, "date_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "output": {"path": str(flac), "sha256": hashlib.sha256(flac.read_bytes()).hexdigest(),
                       "seconds": round(len(audio) / 48000, 2)}, "cost_eur": 0}
    meta.update(json.loads(a.record))
    (a.output / "continuation.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    os.chmod(flac, 0o444)


if __name__ == "__main__":
    main()
