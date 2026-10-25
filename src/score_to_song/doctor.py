"""Read-only check of the environment: tools, engines, weights, separation model, memory. Downloads nothing."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from .util import MLX_YUE_COMMIT, SEPARATION_SHA256, git_commit, separation_dir, sha256_file, yue_dir


def _free_memory_gib() -> float | None:
    if platform.system() != "Darwin":
        return None
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = int(out.split("page size of ")[1].split()[0])
    pages = {line.split(":")[0]: int(line.split(":")[1].strip().rstrip(".")) for line in out.splitlines()[1:] if ":" in line}
    free = sum(pages.get(k, 0) for k in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"))
    return round(free * page / 2**30, 1)


def doctor(engines: Path, hash_models: bool = False) -> int:
    checks = []

    def check(name, ok, detail="", required=True):
        checks.append((name, ok, detail, required))

    check("macOS on Apple Silicon", platform.system() == "Darwin" and platform.machine() == "arm64", f"{platform.system()} {platform.machine()}")
    check("Python >= 3.11 (toolkit)", sys.version_info >= (3, 11), sys.version.split()[0])
    check("ffmpeg", bool(shutil.which("ffmpeg")), shutil.which("ffmpeg") or "brew install ffmpeg")
    for pkg in ("numpy", "soundfile", "pyloudnorm"):
        try:
            check(f"package {pkg}", True, metadata.version(pkg))
        except metadata.PackageNotFoundError:
            check(f"package {pkg}", False, "pip install -e .")
    try:
        check("package audio-separator (separate)", True, metadata.version("audio-separator"), required=False)
    except metadata.PackageNotFoundError:
        check("package audio-separator (separate)", False, "pip install -e '.[separation]'", required=False)
    yue = yue_dir(engines)
    check("engines directory", engines.is_dir(), str(engines))
    commit = git_commit(yue) if yue.is_dir() else None
    check("mlx-Yue checkout", commit is not None, f"{yue} @ {commit[:7] if commit else '-'}")
    if commit and commit != MLX_YUE_COMMIT:
        check("mlx-Yue at the validated commit", False, f"validated with {MLX_YUE_COMMIT[:7]}; others may work", required=False)
    venv = yue / ".venv/bin/python"
    check("mlx-Yue environment", venv.exists(), str(venv) if venv.exists() else "cd mlx-Yue && uv sync --frozen --no-dev")
    paths_file = yue / "models/paths.json"
    if paths_file.exists():
        paths = json.loads(paths_file.read_text())
        for key in ("model", "vae"):
            p = Path(paths.get(key, ""))
            p = p if p.is_absolute() else yue / p
            check(f"YuE2 weights ({key})", p.exists(), str(p))
    else:
        check("YuE2 weights (models/paths.json)", False, "mlx-yue prepare ... > models/paths.json (docs/install.md)")
    sep = separation_dir(engines)
    for name, expected in SEPARATION_SHA256.items():
        p = sep / name
        if not p.exists():
            check(f"separation model {name}", False, "scripts/install.sh --only separation", required=False)
        elif hash_models:
            check(f"separation model {name}", sha256_file(p) == expected, "SHA-256 " + ("as expected" if sha256_file(p) == expected else "differs"), required=False)
        else:
            check(f"separation model {name}", True, "present (use --hash to verify)", required=False)
    free = _free_memory_gib()
    if free is not None:
        check("free memory for a render (10-12 GB)", free >= 12, f"{free} GiB free or reclaimable", required=False)
    width = max(len(c[0]) for c in checks)
    failed = 0
    for name, ok, detail, required in checks:
        mark = "ok  " if ok else ("FAIL" if required else "warn")
        failed += (not ok) and required
        print(f"{mark}  {name.ljust(width)}  {detail}")
    print("\nready" if not failed else f"\n{failed} required check(s) failed; see docs/install.md")
    return 1 if failed else 0
