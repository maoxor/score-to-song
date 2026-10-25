# score-to-song

[![tests](https://github.com/maoxor/score-to-song/actions/workflows/tests.yml/badge.svg)](https://github.com/maoxor/score-to-song/actions/workflows/tests.yml)
[![licence: Apache-2.0](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)
![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue.svg)
![macOS, Apple Silicon](https://img.shields.io/badge/macOS-Apple%20Silicon-lightgrey.svg)

**Write a melody as a score, have YuE2 sing it on your Mac, extend it without losing the voice, layer
more voices, and mix — locally, at no cost, with every file traceable.**

score-to-song is a small command-line toolkit around [YuE2](https://github.com/multimodal-art-projection/YuE)
(an open song-generation model that can follow a symbolic score) and its Apple Silicon port
[mlx-Yue](https://github.com/vanch007/mlx-Yue). It turns a readable score file into the ABC dialect YuE2
reads natively, renders it, continues a validated render with new music, separates the extra voices,
mixes them with plain gains, and writes a provenance record next to every output.

It was built and used to produce a 1 min 56 s wordless piece for three voices (main female voice, male
voice an octave below, high second voice) for a video game soundtrack. That piece is not part of this
repository; [`examples/first-song/`](examples/first-song/) is an original example you can run instead.

---

## Why this exists

Text-to-music generators choose the melody for you: if one note is wrong, you can only roll the dice
again. YuE2 can instead be given a **score** (in a restricted ABC notation) together with a style
description and lyrics, and it sings that score with an accompaniment it generates itself. Using that
in practice raised five problems, and each command of the toolkit answers one of them:

| Problem met in production | What score-to-song does |
|---|---|
| Writing YuE2's native ABC by hand is error-prone: bar lengths, the 11 allowed durations, ties at barlines, accidentals that carry across octaves. | `compose` writes it from a score file where a note is `Bb4:6` (pitch : sixteenths). Bars, ties and accidentals are computed and checked. `import-abc` turns an existing native ABC back into a score file (checked by round trip). |
| Re-rendering a longer score changes the singer: timbre, vibrato and phrasing drift, even with the same seed. | `continue` keeps the sung tokens of a render you like up to a chosen second and lets YuE2 sing the rest of a new score. It checks first that the new score repeats the old one up to that point. |
| YuE2 sings one solo voice per render. | Write the other voices as scores that share tempo, chords and accompaniment (`[derive]`), render them separately, estimate their voice with a source separator (`separate`), and lay them under the main render (`mix`). |
| A mix you cannot rebuild is a mix you cannot fix. | `mix` reads a recipe file (splices, delays, gains, time windows, fades). Outputs are bit-for-bit reproducible WAV files; every output gets a JSON sidecar with its inputs, settings and SHA-256. Nothing is ever overwritten. |
| Louder sounds better, which biases every comparison. | `listen` makes copies at the same loudness (linear gain only) and a local HTML page to compare them. |

The mix stage deliberately uses **only linear gains and short fades**: no reverb, EQ or compression. The
generated material is kept as it is, so what you judge is the composition and the performance.

## What you need

- A Mac with Apple Silicon. A render needs **about 10–12 GB of free memory** (mlx-Yue stops instead of
  swapping); 32 GB of RAM or more is comfortable. Developed on an M5 Max with 64 GB.
- About 11 GB of disk once installed (14 GB more during the one-time weight conversion).
- `git`, `ffmpeg`, `uv` (`brew install git ffmpeg uv`). Python 3.12 is installed by `uv`.
- No account, key or paid service. Everything runs offline once installed.

## Install

```bash
git clone https://github.com/maoxor/score-to-song && cd score-to-song
scripts/install.sh            # toolkit, mlx-Yue (pinned commit), YuE2 weights (download + local conversion), separator
source .venv/bin/activate
score-to-song doctor          # read-only check of everything above
```

Details, options (engines on another disk, reusing existing weights) and manual steps:
[docs/install.md](docs/install.md).

## Your first song

`examples/first-song/` is a complete, original example: a 10-bar melody for a female voice, a male voice
derived from it, and a continuation that adds a bridge and an ending.

```bash
examples/first-song/run.sh    # about 3 minutes on an M5 Max; writes everything to examples/first-song/work/
```

It runs the whole workflow:

```
main.toml ──compose──► ABC + request ──render──► main render (32 s) ──continue──► long render (bridge, ending)
low.toml  ──compose──► ABC + request ──render──► male render ──separate──► male voice estimate
                                                                      │
mix.toml: main render ⟶ splice into the long render, male voice under the chorus ──mix──► mix + loop test
                                                                      │
                                                    listen ──► page with every file at -20 LUFS
```

Then make it yours: change notes in `main.toml`, the voice and instruments in `style`, the chords, the
seed. The step-by-step tutorial is [docs/workflow.md](docs/workflow.md).

## Commands

| Command | Input → output |
|---|---|
| `score-to-song compose SCORE.toml --out DIR` | score file → `<id>.abc` + `req_<id>_s<seed>.json` (one per seed) |
| `score-to-song import-abc FILE.abc [--request REQ.json] --out NEW.toml` | native ABC → editable score file |
| `score-to-song render REQ.json… --out DIR` | requests → one render folder each (`generate/audio.flac`, score, tokens) + provenance |
| `score-to-song continue --source RENDER --keep-s S --request REQ.json --out NEW` | a render + a longer score → a render that keeps the first S seconds |
| `score-to-song separate RENDER… --out DIR` | renders → `<name>_voice_estimate.wav` (48 kHz float) + provenance |
| `score-to-song mix RECIPE.toml` | recipe → WAV + `.wav.json` sidecar (+ optional loop test) |
| `score-to-song listen FILE… --out DIR` | files → loudness-matched copies + `index.html` |
| `score-to-song doctor` | checks tools, engines, weights, separator and free memory |

Formats: [score files](docs/score-format.md) · [mix recipes](docs/mix-recipe.md).

## Repository layout

```
score-to-song/
├── src/score_to_song/        the toolkit (one module per command; abc.py = the native ABC dialect)
│   └── yue_continue_engine.py   continuation, run inside mlx-Yue's own environment
├── examples/first-song/      original example: scores, mix recipe, run.sh
├── docs/                     install, workflow, formats, field notes, rights
├── scripts/install.sh        installs the toolkit and the engines
├── tests/                    unit tests (pytest), no model needed
├── CHANGELOG.md              what changed in each version
├── requirements.lock.txt     exact versions the toolkit was validated with
└── vendor/                   engines (created by install.sh, ignored by Git)
```

## Before you publish anything you make

- **YuE2's weights are not open source software.** They are under CC BY-NC 4.0 with an additional
  permission (2026-09-16) that lets *individual* creators monetise their outputs; companies need a
  commercial licence from the authors. Check which case you are in. See [docs/rights.md](docs/rights.md).
- The licence of a model says nothing about the rights on what you feed it. Do not put names of artists,
  titles or protected recordings into prompts, and write your own melodies.
- Separated voices are **estimates** with some residue of the render's accompaniment, not original
  stems. Present them as such.

## Limits

- YuE2 offers no direct control of glides, breaths or dynamics, and it does not always sing exactly what
  is written: listen to every render. In our renders, female voices sang **one octave below** the
  written pitch (see [docs/field-notes.md](docs/field-notes.md)).
- Renders were bit-identical when repeated on the same machine with the same request, seed, weights and
  mlx-Yue commit. Across machines or MLX versions this is not guaranteed; keep your renders.
- macOS on Apple Silicon only (that is what mlx-Yue supports).

## Contributing

Issues and pull requests are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Security problems go through
[SECURITY.md](SECURITY.md). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Licence

The code is under the [Apache License 2.0](LICENSE). The models it drives keep their own licences: see
[docs/rights.md](docs/rights.md).
