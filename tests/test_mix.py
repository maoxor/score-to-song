import json

import numpy as np
import pytest
import soundfile as sf

from score_to_song.mix import mix
from score_to_song.wavio import encode_wav

SR = 48000


def tone(seconds, freq, amp=0.2, channels=2):
    t = np.arange(int(seconds * SR)) / SR
    x = amp * np.sin(2 * np.pi * freq * t)
    return np.repeat(x[:, None], channels, axis=1)


def write(path, x):
    sf.write(path, x, SR, subtype="FLOAT")
    return path


def test_wav_writer_is_deterministic():
    x = tone(0.1, 440)
    assert encode_wav(x, SR) == encode_wav(x.copy(), SR)
    with pytest.raises(ValueError):
        encode_wav(x * 10, SR, "PCM_24")


def test_splice_layers_gains_and_loop_test(tmp_path):
    a = tone(6, 220)
    b = a.copy()
    b[4 * SR:] = tone(6, 330)[4 * SR:]                  # agrees with a until 4 s, like a continuation
    write(tmp_path / "a.wav", a)
    write(tmp_path / "b.wav", b)
    write(tmp_path / "v.wav", tone(6, 440, 0.1))
    (tmp_path / "r.toml").write_text('''
length = 5.0
output = "{out}/mix.wav"
[paths]
out = "."
[[main]]
file = "a.wav"
[[main]]
file = "b.wav"
at = 3.0
crossfade = 0.2
[[layers]]
file = "v.wav"
delay = 1.0
gain_db = -6.0
windows = [[1.5, 2.5]]
[[gains]]
start = 4.0
db = -3.0
ramp_in = 0.5
[check]
same_as = "a.wav"
until = 1.0
[loop_test]
crossfade = 0.1
preview = 1.0
tail = 1.0
''')
    report = mix(tmp_path / "r.toml")
    out, _ = sf.read(tmp_path / "mix.wav", always_2d=True)
    assert len(out) == 5 * SR
    assert report["main"][1]["correlation"] == 1.0
    assert report["check"]["max_deviation"] == 0.0            # nothing added before 1 s
    np.testing.assert_allclose(out[int(1.2 * SR)], a[int(1.2 * SR)])  # layer silent outside its window
    mid = int(2.0 * SR)
    np.testing.assert_allclose(out[mid], a[mid] + 10 ** (-6 / 20) * tone(6, 440, 0.1)[mid - SR], atol=1e-6)
    np.testing.assert_allclose(out[int(4.8 * SR)], b[int(4.8 * SR)] * 10 ** (-3 / 20), atol=1e-6)
    side = json.loads((tmp_path / "mix.wav.json").read_text())
    assert side["output"]["sha256"] == report["output"]["sha256"]
    assert (tmp_path / "mix_loop_test.wav").exists()
    with pytest.raises(SystemExit):                            # never overwrites
        mix(tmp_path / "r.toml")


def test_splice_refuses_tracks_that_disagree(tmp_path):
    write(tmp_path / "a.wav", tone(4, 220))
    write(tmp_path / "b.wav", tone(4, 331))
    (tmp_path / "r.toml").write_text('[[main]]\nfile = "a.wav"\n[[main]]\nfile = "b.wav"\nat = 2.0\n')
    with pytest.raises(SystemExit, match="correlation"):
        mix(tmp_path / "r.toml", tmp_path / "o.wav")


def test_level_matching_and_peak_guard(tmp_path):
    write(tmp_path / "a.wav", tone(3, 220, 0.1))
    write(tmp_path / "ref.wav", tone(3, 440, 0.1))
    write(tmp_path / "v.wav", tone(3, 660, 0.4))
    (tmp_path / "r.toml").write_text('[[main]]\nfile = "a.wav"\n[[layers]]\nfile = "v.wav"\n'
                                     'level = { match = "ref.wav", offset_lu = -6 }\n')
    report = mix(tmp_path / "r.toml", tmp_path / "o.wav")
    assert report["layers"][0]["gain_db"] < -12            # 0.4 -> about 6 LU under the 0.1 reference
    (tmp_path / "loud.toml").write_text('[[main]]\nfile = "a.wav"\n[[layers]]\nfile = "v.wav"\ngain_db = 9.0\n')
    with pytest.raises(SystemExit, match="peak"):
        mix(tmp_path / "loud.toml", tmp_path / "p.wav")
