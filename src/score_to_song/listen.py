"""Listening page: copies of the given files brought to one loudness by linear gain only (default -20 LUFS,
lowered for every file if one would exceed -1 dBFS sample peak), plus a local HTML page to compare them.
This is for fair A/B listening, not mastering. Nothing is uploaded anywhere.
"""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import soundfile as sf

from .mix import loudness
from .util import now_utc, rel, sha256_file, tool_info, write_json
from .wavio import write_wav


def parse_item(text: str) -> dict:
    """'file.wav', 'file.wav@10-25' (seconds) or 'Label=file.wav@10-25'."""
    label, _, rest = text.rpartition("=") if "=" in text else ("", "", text)
    path, _, span = rest.partition("@")
    item = {"path": Path(path), "label": label or Path(path).stem}
    if span:
        a, _, b = span.partition("-")
        item["start"], item["end"] = float(a), (float(b) if b else None)
    return item


def build(items: list[dict], out_dir: Path, target: float = -20.0, ceiling_db: float = -1.0, title: str = "Listening") -> dict:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"{rel(out_dir)} exists and is not empty; choose a new folder")
    out_dir.mkdir(parents=True, exist_ok=True)
    loaded = []
    for it in items:
        x, sr = sf.read(it["path"], always_2d=True)
        a, b = int(it.get("start", 0) * sr), it.get("end")
        x = x[a:int(b * sr) if b else None]
        lufs = loudness(x, sr)
        if not np.isfinite(lufs):
            raise SystemExit(f"{it['path']}: silent or too short to measure")
        loaded.append((it, x, sr, lufs))
    ceiling = 10 ** (ceiling_db / 20)
    # common target, lowered if any copy would clip
    worst = max(float(np.max(np.abs(x))) * 10 ** ((target - lufs) / 20) for _, x, _, lufs in loaded)
    effective = target - max(0.0, 20 * np.log10(worst / ceiling))
    entries = []
    for k, (it, x, sr, lufs) in enumerate(loaded, start=1):
        gain_db = effective - lufs
        name = f"{k:02d}_{''.join(c if c.isalnum() or c in '-_' else '_' for c in it['label'])}.wav"
        sha = write_wav(out_dir / name, x * 10 ** (gain_db / 20), sr, "PCM_24")
        entries.append({"label": it["label"], "source": rel(it["path"]), "source_sha256": sha256_file(it["path"]),
                        "span_s": [it.get("start", 0), it.get("end")], "source_lufs": round(lufs, 2), "gain_db": round(gain_db, 2),
                        "copy": name, "copy_sha256": sha})
    rows = "\n".join(f'<section><h2>{html.escape(e["label"])}</h2><p>{html.escape(e["source"])} · {e["source_lufs"]} LUFS · '
                     f'gain {e["gain_db"]:+.2f} dB</p><audio controls preload="none" src="{e["copy"]}"></audio></section>' for e in entries)
    (out_dir / "index.html").write_text(f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;background:#fff;color:#111}}
section{{border-top:1px solid #ccc;padding:.75rem 0}}h2{{font-size:1.05rem;margin:0}}p{{margin:.2rem 0;color:#555;font-size:.9rem}}
audio{{width:100%}}@media (prefers-color-scheme: dark){{body{{background:#111;color:#eee}}p{{color:#aaa}}section{{border-color:#333}}}}</style>
<h1>{html.escape(title)}</h1><p>All copies at {effective:.1f} LUFS by linear gain only (no other processing). Listen at one fixed volume.</p>
{rows}
</html>
""", encoding="utf-8")
    report = {"tool": tool_info(), "target_lufs": target, "effective_lufs": round(effective, 2), "ceiling_dbfs": ceiling_db,
              "date_utc": now_utc(), "items": entries}
    write_json(out_dir / "listening.json", report)
    return report
