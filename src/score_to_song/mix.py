"""Mix from a recipe (TOML): a main track spliced from renders, voice layers placed by delay, gain and time
windows, gain automation, a length, a loop test. Linear gains and fades only: no reverb, EQ or compression.
See docs/mix-recipe.md. Every output gets a .json sidecar with its inputs, settings and SHA-256.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import numpy as np
import soundfile as sf

from .util import now_utc, rel, sha256_file, tool_info, write_json
from .wavio import write_wav

TOP = {"sample_rate", "root", "paths", "output", "format", "length", "peak_max", "on_peak", "main", "layers", "gains",
       "check", "loop_test", "note"}
MAIN = {"file", "at", "crossfade", "curve", "min_correlation"}
LAYER = {"file", "delay", "gain_db", "level", "windows", "fade", "enter_at", "enter_fade", "label"}
GAIN = {"start", "end", "db", "ramp_in", "ramp_out"}


class Recipe:
    def __init__(self, path: Path, overrides: dict[str, str] | None = None):
        self.path = Path(path).resolve()
        with self.path.open("rb") as f:
            self.data = tomllib.load(f)
        unknown = set(self.data) - TOP
        if unknown:
            raise ValueError(f"{path}: unknown fields {sorted(unknown)}")
        self.root = (self.path.parent / self.data.get("root", ".")).resolve()
        # [paths] values are relative to root; --path values given on the command line, to the working directory
        self.paths = {k: str(v) for k, v in self.data.get("paths", {}).items()}
        self.paths.update({k: str(Path(v).expanduser().resolve()) for k, v in (overrides or {}).items()})
        self.sr = int(self.data.get("sample_rate", 48000))
        self.cache: dict[Path, np.ndarray] = {}

    def file(self, value: str) -> Path:
        def sub(m):
            if m.group(1) not in self.paths:
                raise ValueError(f"unknown path variable {{{m.group(1)}}}; define it in [paths] or with --path")
            return self.paths[m.group(1)]
        p = Path(re.sub(r"\{(\w+)\}", sub, value)).expanduser()
        return p if p.is_absolute() else self.root / p

    def read(self, value: str) -> np.ndarray:
        p = self.file(value)
        if not p.exists():
            raise FileNotFoundError(f"{p} (from {value!r} in {self.path.name})")
        if p not in self.cache:
            x, sr = sf.read(p, always_2d=True)
            if sr != self.sr:
                raise ValueError(f"{p}: {sr} Hz, the recipe works at {self.sr} Hz (convert with ffmpeg -ar {self.sr})")
            self.cache[p] = x
        return self.cache[p]


def place(n: int, channels: int, voice: np.ndarray, delay: float, gain: float, sr: int) -> np.ndarray:
    """The voice's time 0 lands at `delay` seconds (negative: its start is cut). Linear gain."""
    if voice.shape[1] != channels:
        voice = np.repeat(voice[:, :1], channels, axis=1) if voice.shape[1] == 1 else voice[:, :channels]
    out = np.zeros((n, channels))
    d = int(round(delay * sr))
    src = voice[max(0, -d):]
    m = max(0, min(len(src), n - max(0, d)))
    out[max(0, d):max(0, d) + m] = src[:m] * gain
    return out


def window(n: int, segments, fade: float, sr: int) -> np.ndarray:
    """1 inside the segments, 0 outside, linear fades of `fade` seconds inside each segment's edges."""
    mask = np.zeros(n)
    f = int(fade * sr)
    for s, e in segments:
        i, j = int(s * sr), min(int(e * sr), n)
        mask[i:j] = 1.0
        mask[i:i + f] = np.linspace(0, 1, len(mask[i:i + f]))
        mask[max(j - f, 0):j] = np.minimum(mask[max(j - f, 0):j], np.linspace(1, 0, len(mask[max(j - f, 0):j])))
    return mask[:, None]


def entry(n: int, start: float, fade: float, sr: int) -> np.ndarray:
    """0 before `start`, linear fade-in over `fade` seconds, then 1."""
    ramp = np.zeros(n)
    s0, f = int(start * sr), int(fade * sr)
    ramp[s0:s0 + f] = np.linspace(0, 1, len(ramp[s0:s0 + f]))
    ramp[s0 + f:] = 1.0
    return ramp[:, None]


def loudness(x: np.ndarray, sr: int) -> float:
    import pyloudnorm
    return pyloudnorm.Meter(sr).integrated_loudness(x)


def _main_track(r: Recipe, report: dict) -> np.ndarray:
    entries = r.data.get("main", [])
    if not entries:
        raise ValueError("the recipe needs at least one [[main]] entry (the track the layers are added to)")
    for e in entries:
        if set(e) - MAIN:
            raise ValueError(f"[[main]] unknown fields {sorted(set(e) - MAIN)}")
    track = r.read(entries[0]["file"])
    report["main"] = [{"path": rel(r.file(entries[0]["file"])), "sha256": sha256_file(r.file(entries[0]["file"]))}]
    for e in entries[1:]:
        nxt, sr = r.read(e["file"]), r.sr
        end, n = int(e["at"] * sr), int(e.get("crossfade", 0.2) * sr)
        start = end - n
        curve = e.get("curve", "linear")
        corr = float(np.corrcoef(track[start:end].ravel(), nxt[start:end].ravel())[0, 1])
        threshold = e.get("min_correlation", 0.8 if curve == "linear" else None)
        if threshold is not None and corr < threshold:
            raise SystemExit(f"splice at {e['at']} s: the tracks differ in the crossfade (correlation {corr:.2f} < {threshold}); "
                             "a continuation should sing the same thing up to its keep point")
        x = np.linspace(0, 1, n)[:, None]
        if curve == "linear":
            mixed = track[start:end] * (1 - x) + nxt[start:end] * x
        elif curve == "equal-power":
            mixed = track[start:end] * np.cos(x * np.pi / 2) + nxt[start:end] * np.sin(x * np.pi / 2)
        else:
            raise ValueError(f"curve must be 'linear' or 'equal-power', not {curve!r}")
        track = np.concatenate([track[:start], mixed, nxt[end:]])
        report["main"].append({"path": rel(r.file(e["file"])), "sha256": sha256_file(r.file(e["file"])), "at_s": e["at"],
                               "crossfade_s": n / sr, "curve": curve, "correlation": round(corr, 3)})
    return track


def _layer(r: Recipe, spec: dict, n: int, channels: int) -> tuple[np.ndarray, dict]:
    if set(spec) - LAYER:
        raise ValueError(f"[[layers]] unknown fields {sorted(set(spec) - LAYER)}")
    if ("gain_db" in spec) == ("level" in spec):
        raise ValueError(f"layer {spec.get('file')}: give either gain_db or level, not both or neither")
    sr, voice = r.sr, r.read(spec["file"])
    delay = float(spec.get("delay", 0.0))
    env = []
    if "enter_at" in spec:
        env.append(entry(n, float(spec["enter_at"]), float(spec.get("enter_fade", 1.0)), sr))
    if "windows" in spec:
        env.append(window(n, [tuple(w) for w in spec["windows"]], float(spec.get("fade", 0.15)), sr))
    info = {"path": rel(r.file(spec["file"])), "sha256": sha256_file(r.file(spec["file"])), "delay_s": delay}
    if "gain_db" in spec:
        layer = place(n, channels, voice, delay, 10 ** (float(spec["gain_db"]) / 20), sr)
        for e in env:
            layer = layer * e
        info["gain_db"] = float(spec["gain_db"])
    else:
        lv = spec["level"]
        ref = r.read(lv["match"])
        offset, measure = float(lv.get("offset_lu", 0.0)), lv.get("measure", "source")
        if measure == "source":       # sung level of the whole take against the whole reference voice
            gain_db = loudness(ref, sr) + offset - loudness(voice, sr)
            layer = place(n, channels, voice, delay, 10 ** (gain_db / 20), sr)
            for e in env:
                layer = layer * e
        elif measure == "placed":     # the layer as heard in the mix against the reference over the mix length
            layer = place(n, channels, voice, delay, 1.0, sr)
            for e in env:
                layer = layer * e
            gain_db = loudness(ref[:n], sr) + offset - loudness(layer, sr)
            layer = layer * 10 ** (gain_db / 20)
        else:
            raise ValueError("level.measure must be 'source' or 'placed'")
        info.update({"level": {"match": rel(r.file(lv["match"])), "offset_lu": offset, "measure": measure}, "gain_db": gain_db})
    for key in ("windows", "fade", "enter_at", "enter_fade", "label"):
        if key in spec:
            info[key] = spec[key]
    return layer, info


def _gain_curve(spec: dict, n: int, sr: int) -> np.ndarray:
    if set(spec) - GAIN:
        raise ValueError(f"[[gains]] unknown fields {sorted(set(spec) - GAIN)}")
    g_lin = 10 ** (float(spec["db"]) / 20)
    g = np.ones(n)
    i0 = int(spec["start"] * sr)
    if "end" not in spec:            # ramp in, then hold to the end
        r = int(float(spec.get("ramp_in", 1.0)) * sr)
        g[i0:i0 + r] = np.linspace(1.0, g_lin, len(g[i0:i0 + r]))
        g[i0 + r:] = g_lin
    else:                            # ramp in, hold, ramp out
        i1 = min(int(spec["end"] * sr), n)
        ri, ro = int(float(spec.get("ramp_in", 1.0)) * sr), int(float(spec.get("ramp_out", 1.0)) * sr)
        g[i0:i1] = g_lin
        g[i0:i0 + ri] = np.linspace(1.0, g_lin, len(g[i0:i0 + ri]))
        g[max(i1 - ro, i0):i1] = np.linspace(g_lin, 1.0, len(g[max(i1 - ro, i0):i1]))
    return g[:, None]


def mix(recipe_path: Path, out: Path | None = None, overrides: dict[str, str] | None = None) -> dict:
    r = Recipe(recipe_path, overrides)
    d, sr = r.data, r.sr
    out = Path(out) if out else r.file(d.get("output", r.path.stem + ".wav"))
    if out.exists():
        raise SystemExit(f"{rel(out)} exists; nothing is overwritten (choose another output)")
    report: dict = {"recipe": {"path": rel(r.path), "sha256": sha256_file(r.path)}, "tool": tool_info(), "path_variables": r.paths}
    track = _main_track(r, report)
    n = int(d["length"] * sr) if "length" in d else len(track)
    track = track[:n] if len(track) >= n else np.pad(track, ((0, n - len(track)), (0, 0)))
    channels = track.shape[1]
    total = track
    report["layers"] = []
    for spec in d.get("layers", []):
        layer, info = _layer(r, spec, n, channels)
        total = total + layer
        report["layers"].append(info)
    for spec in d.get("gains", []):
        total = total * _gain_curve(spec, n, sr)
    report["gains"] = d.get("gains", [])
    if "check" in d:
        c = d["check"]
        ref, until = r.read(c["same_as"]), int(c["until"] * sr)
        dev = float(np.max(np.abs(total[:until] - ref[:until])))
        report["check"] = {"same_as": rel(r.file(c["same_as"])), "until_s": c["until"], "max_deviation": dev}
        if "max_deviation" in c and dev > c["max_deviation"]:
            raise SystemExit(f"check failed: deviation {dev:.3g} from {c['same_as']} before {c['until']} s")
    peak, peak_max = float(np.max(np.abs(total))), float(d.get("peak_max", 0.891))
    trim = 1.0
    if peak > peak_max:
        if d.get("on_peak", "fail") == "trim":
            trim = peak_max / peak
            total = total * trim
        else:
            raise SystemExit(f"peak {peak:.3f} above {peak_max} ({20 * np.log10(peak_max):.1f} dBFS); lower the layers or set on_peak = \"trim\"")
    fmt = {"float": "FLOAT", "pcm24": "PCM_24"}[d.get("format", "float")]
    sha = write_wav(out, total, sr, fmt)
    report.update({"length_s": round(n / sr, 4), "peak_before_trim": round(peak, 4), "peak": round(peak * trim, 4), "trim_db": round(20 * np.log10(trim), 2), "effects": "none",
                   "date_utc": now_utc(), "output": {"path": rel(out), "sha256": sha, "format": f"WAV {sr} Hz {d.get('format', 'float')}"}})
    if "loop_test" in d:
        lt = d["loop_test"]
        x = int(float(lt.get("crossfade", 0.5)) * sr)
        head = r.read(lt["start_from"]) if "start_from" in lt else total
        fade = np.linspace(0, 1, x)[:, None]
        preview = np.concatenate([total[:-x], total[-x:] * np.cos(fade * np.pi / 2) + head[:x] * np.sin(fade * np.pi / 2),
                                  head[x:int(float(lt.get("preview", 12.0)) * sr)]])
        loop_path = r.file(lt["file"]) if "file" in lt else out.with_name(out.stem + "_loop_test.wav")
        tail = int((float(lt.get("preview", 12.0)) + float(lt.get("tail", 14.0))) * sr)
        report["loop_test"] = {"path": rel(loop_path), "sha256": write_wav(loop_path, preview[-tail:], sr, "FLOAT"),
                               "crossfade_s": x / sr, "start_from": rel(r.file(lt["start_from"])) if "start_from" in lt else "the mix itself"}
    write_json(out.with_suffix(".wav.json"), report)
    return report
