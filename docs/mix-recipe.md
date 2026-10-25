# Mix recipes

`score-to-song mix recipe.toml` builds one WAV file from renders and voice estimates. Operations are
linear gains, delays, crossfades and short fades only. All inputs must be at the recipe's sample rate
(48 kHz, as YuE2 renders and `separate` outputs are).

## Top level

| Field | Default | Meaning |
|---|---|---|
| `output` | `<recipe name>.wav` | output file; refused if it exists (`--out` overrides) |
| `root` | the recipe's folder | base folder of relative paths |
| `[paths]` | — | named folders used as `{name}/file.wav`; `--path name=DIR` overrides one from the command line (relative to the working directory) |
| `length` | length of the main track | seconds; the mix is cut or padded with silence |
| `format` | `float` | `float` (32-bit) or `pcm24` |
| `peak_max` | `0.891` | highest allowed sample (−1 dBFS) |
| `on_peak` | `fail` | `fail`, or `trim` (one linear gain on the whole mix) |
| `sample_rate` | `48000` | |
| `note` | — | free text, kept in the recipe |

## `[[main]]` — the main track

The first entry is a file. Each following entry splices another file in:

| Field | Default | Meaning |
|---|---|---|
| `file` | | audio file (a render's `generate/audio.flac`) |
| `at` | | end of the crossfade, in seconds |
| `crossfade` | `0.2` | seconds, ending at `at` |
| `curve` | `linear` | `linear` or `equal-power` |
| `min_correlation` | `0.8` (linear) | the two tracks must agree in the crossfade; a continuation sings the same thing up to its keep point, so splice just before `keep-s` |

## `[[layers]]` — voices added to the main track

| Field | Default | Meaning |
|---|---|---|
| `file` | | voice estimate (or any audio) |
| `delay` | `0.0` | where the file's time 0 lands, in seconds; negative cuts its start |
| `gain_db` | | fixed gain, **or** |
| `level` | | `{ match = "ref.wav", offset_lu = -4, measure = "source" }`: gain so that the layer sits `offset_lu` loudness units from the reference. `measure = "source"` compares the whole files (the sung level of the take); `"placed"` measures the layer as placed and enveloped in the mix, against the reference cut to the mix length |
| `windows` | whole file | `[[start, end], …]` in mix time: heard only there |
| `fade` | `0.15` | fades inside each window's edges, seconds |
| `enter_at` | — | silent before, then a linear fade-in of `enter_fade` (default 1 s) |
| `label` | — | name kept in the sidecar |

Layers are summed in the order written. The same file can appear several times with different delays
and windows (e.g. one take placed at two moments).

## `[[gains]]` — gain automation, applied in order after the layers

| Field | Meaning |
|---|---|
| `start`, `db` | from `start`, ramp to `db` over `ramp_in` seconds (default 1) |
| `end` | optional: hold until `end`, then ramp back to 0 dB over `ramp_out` (default 1). Without `end`, the gain holds to the end of the mix |

## `[check]`

```toml
[check]
same_as = "previous_version.wav"
until = 43.3          # seconds
max_deviation = 0.0   # optional: fail above this
```

Reports the largest sample difference with another file before `until`: useful to prove that a new
version leaves an approved passage untouched.

## `[loop_test]`

Writes `<output>_loop_test.wav` (or `file`): the last `tail` seconds (default 14) of the mix crossfaded
(`crossfade`, default 0.5 s, equal power) into the first `preview` seconds (default 12) of `start_from`
(default: the mix itself). Listen to it to judge a loop point.

## The sidecar

Every mix writes `<output>.wav.json`: recipe path and SHA-256, toolkit version and commit, every input
with its SHA-256, the gain actually applied to each layer, splice correlations, peak, check result, the
output's SHA-256. The WAV writer emits no timestamped chunks, so identical samples give identical files.
