"""Shared helpers: engine locations, hashing, timestamps, provenance paths."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

from . import __version__

# Versions the toolkit was validated with (docs/install.md). Other versions may work; doctor reports them.
MLX_YUE_REPO = "https://github.com/vanch007/mlx-Yue"
MLX_YUE_COMMIT = "c5b5a8190f78c74aa671a4caa19dae8b8e04b3d8"
WEIGHTS = {"generator": {"repo": "m-a-p/YuE2-3B", "revision": "1a96eca688d6ae5d7f0feb88573fec89920fcd19"},
           "vae": {"repo": "m-a-p/YuE2-Vae", "revision": "95535e72a97bc0f09b8ada125d26b4009428c0e8"},
           "license": "CC BY-NC 4.0 + additional permission for individual creators (2026-09-16), "
                      "https://github.com/multimodal-art-projection/YuE/blob/main/MODEL_LICENSE",
           "conversion": "local, mlx-yue prepare --precision bf16 (pre-converted community weights not used)"}
SEPARATION_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
SEPARATION_SHA256 = {"model_bs_roformer_ep_317_sdr_12.9755.ckpt": "5b84f37e8d444c8cb30c79d77f613a41c05868ff9c9ac6c7049c00aefae115aa",
                     "model_bs_roformer_ep_317_sdr_12.9755.yaml": "2bfdd16c656bd9519aba757cc4f8834b7ede675eb1e00ec4772d74ae1c41af7f"}


def engines_dir(value: str | Path | None = None) -> Path:
    """Where mlx-Yue and the separation model live: --engines, else $SCORE_TO_SONG_ENGINES, else ./vendor."""
    return Path(value or os.environ.get("SCORE_TO_SONG_ENGINES") or "vendor").expanduser().resolve()


def yue_dir(engines: Path) -> Path:
    return engines / "mlx-Yue"


def separation_dir(engines: Path) -> Path:
    return engines / "models" / "separation"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    """Path as recorded in provenance: relative to the working directory when inside it."""
    path = Path(path).resolve()
    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def git_commit(directory: Path) -> str | None:
    p = subprocess.run(["git", "-C", str(directory), "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


def tool_info() -> dict:
    """Version of score-to-song, plus its Git commit when run from a checkout of this repository."""
    here = Path(__file__).resolve().parent
    top = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    # an installed copy may sit inside some other Git work tree (e.g. a .venv in a project): not our commit
    ours = top.returncode == 0 and Path(top.stdout.strip()).resolve() / "src" / "score_to_song" == here
    commit = git_commit(here) if ours else None
    dirty = None
    if commit:
        status = subprocess.run(["git", "-C", str(here), "status", "--porcelain", "--", "."], capture_output=True, text=True)
        dirty = bool(status.stdout.strip())
    return {"name": "score-to-song", "version": __version__, "commit": commit, "uncommitted_changes": dirty}


def write_json(path: Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
