"""Estimate the sung voice of a render with BS-RoFormer (audio-separator), then bring it to 48 kHz float.

Steps (as in the validated workflow): FLAC -> WAV 24-bit (ffmpeg), audio-separator with the BS-RoFormer
model -> 'Vocals' stem at 44.1 kHz, ffmpeg -ar 48000 -c:a pcm_f32le. The result is an ESTIMATE: it keeps a
little of the render's own accompaniment. It is not an original stem.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

from .util import SEPARATION_MODEL, now_utc, rel, separation_dir, sha256_file, tool_info, write_json


def _ffmpeg_version() -> str | None:
    p = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    return p.stdout.splitlines()[0] if p.returncode == 0 else None


def resolve_input(path: Path) -> Path:
    """A render directory (uses generate/audio.flac) or an audio file."""
    path = Path(path)
    if path.is_dir():
        flac = path / "generate/audio.flac"
        if not flac.exists():
            raise SystemExit(f"{path} has no generate/audio.flac")
        return flac
    return path


def separate(inputs: list[Path], out_dir: Path, engines: Path, names: list[str] | None = None, keep_instrumental: bool = False,
             suffix: str = "_voice_estimate") -> list[dict]:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found (brew install ffmpeg)")
    cli = Path(sys.executable).parent / "audio-separator"
    if not cli.exists():
        raise SystemExit("audio-separator is not installed in this environment: pip install 'score-to-song[separation]'")
    model_dir = separation_dir(engines)
    if not (model_dir / SEPARATION_MODEL).exists():
        raise SystemExit(f"missing {model_dir / SEPARATION_MODEL}; run scripts/install.sh (docs/install.md)")
    if names and len(names) != len(inputs):
        raise SystemExit(f"{len(names)} --name for {len(inputs)} inputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for k, item in enumerate(inputs):
        src = resolve_input(item)
        name = names[k] if names else (Path(item).name if Path(item).is_dir() else src.stem)
        out = out_dir / f"{name}{suffix}.wav"
        if out.exists():
            print(f"{rel(out)} exists, skipped", flush=True)
            continue
        with tempfile.TemporaryDirectory(prefix="score-to-song-sep-") as tmp:
            t = Path(tmp)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-c:a", "pcm_s24le", str(t / f"{name}.wav")], check=True)
            log = t / "separator.log"
            with log.open("w") as handle:
                p = subprocess.run([str(cli), str(t / f"{name}.wav"), "-m", SEPARATION_MODEL, "--model_file_dir", str(model_dir),
                                    "--output_dir", str(t), "--output_format", "WAV"], stdout=handle, stderr=subprocess.STDOUT)
            if p.returncode != 0:
                raise SystemExit(f"audio-separator failed on {src}:\n{log.read_text()[-2000:]}")
            stems = {kind: sorted(t.glob(f"{name}_({kind})_*.wav")) for kind in ("Vocals", "Instrumental")}
            if not stems["Vocals"]:
                raise SystemExit(f"no Vocals stem produced for {src}")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(stems["Vocals"][0]), "-ar", "48000", "-c:a", "pcm_f32le", str(out)], check=True)
            outputs = {"voice_estimate": {"path": rel(out), "sha256": sha256_file(out)}}
            if keep_instrumental and stems["Instrumental"]:
                inst = out_dir / f"{name}_accompaniment_estimate.wav"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(stems["Instrumental"][0]), "-ar", "48000", "-c:a", "pcm_f32le", str(inst)], check=True)
                outputs["accompaniment_estimate"] = {"path": rel(inst), "sha256": sha256_file(inst)}
        meta = {"nature": "separation estimate (not an original stem): contains residue of the render's accompaniment",
                "tool": tool_info(), "input": {"path": rel(src), "sha256": sha256_file(src)},
                "separator": {"package": "audio-separator", "version": metadata.version("audio-separator"), "model": SEPARATION_MODEL,
                              "model_sha256": sha256_file(model_dir / SEPARATION_MODEL)},
                "conversion": "ffmpeg: input -> pcm_s24le; Vocals stem -> -ar 48000 pcm_f32le", "ffmpeg": _ffmpeg_version(),
                "date_utc": now_utc(), "outputs": outputs}
        write_json(out.with_suffix(".wav.json"), meta)
        print(f"{rel(out)}", flush=True)
        results.append(meta)
    return results
