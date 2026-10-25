# first-song

An original example of the whole workflow: a 10-bar wordless song in A minor for a female voice, a male
voice doubling it an octave lower in the chorus, and a continuation that adds a bridge and an ending.

| File | Role |
|---|---|
| `main.toml` | main voice: intro (2 bars), verse (4), chorus (4), 76 BPM, ostinato accompaniment |
| `low.toml` | `[derive]` of `main.toml`: one octave lower, held notes, silent in the verse, male voice style |
| `main_long.toml` | `[extend]` of `main.toml`: the same 10 bars, then a bridge and an ending over a drone |
| `mix.toml` | main render spliced into the continuation at 30 s, male voice estimate under the chorus |
| `run.sh` | runs every step; already finished steps are skipped |

```bash
./run.sh          # or step by step: see docs/workflow.md
open work/listen_*/index.html
```

## What a run produced (2026-10-25, M5 Max 64 GB, mlx-Yue c5b5a81, seed 20261025)

| Step | Result (measured) |
|---|---|
| render `first_song_main` | 51.2 s of audio in 24 s of computation; the voice enters at about 6 s (bar 3) |
| render `first_song_low` | 32.3 s; its voice estimate is silent until 19 s and sings from 19 to 27.5 s, the chorus |
| continue, keep 30.5 s | 68.8 s; 762 tokens kept, 958 generated, score check: 10 bars identical |
| mix | 68.8 s; splice correlation 0.985 at 30 s; low voice +0.67 dB to sit 4 LU under the main voice; trim −0.08 dB (the main render alone peaks at 0.899) |
| whole run | about 3 minutes, including model loading and separation |

SHA-256 of that run: main render `5e444415…`, low render `9e9d4e39…`, continuation `a1eec8f9…`,
mix `a4421c2b…`. The same machine, weights and commit should give the same files; another Mac or MLX
version may not.

This run was checked by measurement only, not by ear: listen before you draw conclusions, and change
the seed if a take does not convince you.

## Make it yours

- Change the notes of `main.toml`; keep one chord per bar and the `|` bar checks.
- Change `style` for another voice or other instruments (English, no artist names).
- Try `seeds = [1, 2, 3]` and keep the take you prefer: its request id carries the seed.
- `run.sh` uses seed 20261025 (variable `SEED`); if you change `seeds`, change it there too.
- Renders are never replaced: after editing a score, `render` stops if a folder was made from the
  previous version. Change the seed (or the `id`), or move `work/` away, then run again.
