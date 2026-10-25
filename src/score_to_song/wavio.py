"""Deterministic WAV writing: identical samples always give identical bytes.

libsndfile adds a timestamped PEAK chunk to float WAV files, which changes the file
hash between identical renders. These writers emit only fmt/fact/data chunks.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import numpy as np


def _frames(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio)
    if audio.ndim == 1:
        audio = audio[:, None]
    if not np.isfinite(audio).all():
        raise ValueError("non-finite samples")
    return audio


def encode_wav(audio: np.ndarray, sample_rate: int, subtype: str = "FLOAT") -> bytes:
    """audio: (frames, channels). subtype FLOAT (32-bit IEEE) or PCM_24."""
    audio = _frames(audio)
    frames, channels = audio.shape
    if subtype == "FLOAT":
        payload = audio.astype("<f4").tobytes()
        fmt = struct.pack("<HHIIHHH", 3, channels, sample_rate, sample_rate * channels * 4,
                          channels * 4, 32, 0)
        chunks = [(b"fmt ", fmt), (b"fact", struct.pack("<I", frames))]
    elif subtype == "PCM_24":
        if np.max(np.abs(audio)) > 1.0:
            raise ValueError("PCM_24 would clip: peak above 0 dBFS")
        ints = np.round(audio * 8388607.0).astype("<i4")
        payload = ints.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
        fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, sample_rate * channels * 3,
                          channels * 3, 24)
        chunks = [(b"fmt ", fmt)]
    else:
        raise ValueError(f"unsupported subtype {subtype}")
    chunks.append((b"data", payload))
    body = b"WAVE"
    for tag, data in chunks:
        body += tag + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")
    return b"RIFF" + struct.pack("<I", len(body)) + body


def write_wav(path: Path, audio: np.ndarray, sample_rate: int, subtype: str = "FLOAT",
              overwrite: bool = False) -> str:
    """Write and return the SHA-256 of the file. Refuses to replace a file unless asked."""
    data = encode_wav(audio, sample_rate, subtype)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb" if overwrite else "xb") as target:
        target.write(data)
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
