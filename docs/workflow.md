# The workflow, step by step

This page explains how the mechanism works and how to use it for your own music. The commands below are
the ones `examples/first-song/run.sh` runs; open the files of that folder next to this page.

```
 1 compose      score.toml ───────────────► score.abc + req_<id>_s<seed>.json
 2 render       request ──────────────────► render/  (audio.flac, score, semantic tokens, noise, provenance)
 3 continue     render + longer score ────► new render: same voice up to keep-s, new music after
 4 separate     render of an extra voice ─► voice estimate (48 kHz float WAV)
 5 mix          recipe.toml ──────────────► mix.wav (+ loop test) + mix.wav.json
 6 listen       files ────────────────────► loudness-matched copies + index.html
                      ▲                                                        │
                      └──────────── your ears decide what to change ◄──────────┘
```

## 1. Write the score — `compose`

A score file describes sections. Each section has **one chord per bar**, a melody, the lyric lines and
an accompaniment pattern:

```toml
id = "first_song_main"
tempo = 76
key = "Am"
seeds = [20261025]
style = "Soft clear female solo voice singing a slow wordless melody on open vowels, ..."

[[sections]]
name = "verse"
chords = ["Am", "F", "C", "G"]
melody = "A4:8 E5:8 | F5:12 E5:4 | G5:8 F5:4 E5:4 | D5:12 r:4"
lyrics = ["Ah ah", "Ah oh ah"]
```

A note is `PITCH:UNITS`: `A4` is the A above middle C, `Bb4`, `C#5`; one unit is a sixteenth note, so a
4/4 bar holds 16. `r:4` is a rest, `A4:4~` ties into the next note, `|` checks that a bar is complete.

```bash
score-to-song compose main.toml --out work/scores
```

writes `work/scores/first_song_main.abc` (YuE2's native two-voice ABC: `Vocal` and `Ins`) and one
request per seed. Look at the ABC: notes longer than the room left in a bar are split and tied, lengths
the dialect cannot write in one token (5, 7, 10…) are split, and every accidental is explicit, so the
key signature never changes a pitch behind your back.

The **style** is the main creative lever besides the notes: describe the voice (timbre, vibrato or
straight tone, legato), the instruments, what to avoid (`no drums, no echo`), tempo and key. Write it
in English. **Never put an artist's name, a title or a recording in it**, and write your own melodies.

The **lyrics** are lines per section; wordless vowels (`Ah`, `Oh ah`) work well for a sung instrument.
Each section becomes a `[Verse]`, `[Chorus]`… block; a section without lyrics is played but not sung.

Full format: [score-format.md](score-format.md). To start from an existing native ABC (for example the
`generate/score.abc` of a render), use `score-to-song import-abc`.

## 2. Render — `render`

```bash
score-to-song render work/scores/req_first_song_main_s20261025.json --out work/renders
```

One render at a time, each in `work/renders/<request id>/`:

| File | Content |
|---|---|
| `generate/audio.flac` | the song, 48 kHz stereo, made read-only |
| `generate/request.json`, `score.abc` | what was actually sent to the model |
| `generate/semantic.npy`, `noise.npy` | the sung tokens (25 per second) and the initial noise: what `continue` reuses |
| `<id>.json` (next to the folder) | provenance: tool and mlx-Yue commits, weights and licence, request, seed, date, SHA-256 of the audio |
| `<id>.log` | the engine's output |

A folder that already exists is skipped: nothing is ever re-rendered over a result. On an M5 Max a
51 s render took 24 s of computation (plus loading); slower Macs take longer. `--profile fast`
(8 diffusion steps instead of 32) is quicker for auditions. The render is usually longer than the
score: YuE2 often goes on after the last written bar. Keep what you need when mixing.

**Try several seeds** (`seeds = [1, 2, 3]` gives three requests): the same score sings differently with
each seed. Keep the ones you like; their seed is in the request and the provenance file.

## 3. Extend without losing the voice — `continue`

Rendering a longer version of a score you like gives a different performance: the voice drifts in timbre
and phrasing even with the same seed. A continuation avoids that. YuE2 generates *semantic tokens*
(25 per second) and then turns them into sound. `continue` imposes the tokens of the source render up
to `--keep-s` seconds, and lets the model generate what follows under a new, longer score. The acoustic
stage reuses the source's noise for the kept part, so the kept passage sounds the same.

The new score must repeat the source score exactly up to that point. An `[extend]` score file does this
for you: it takes every section of the source unchanged and adds new ones.

```toml
id = "first_song_long"
[extend]
from = "main.toml"
[[sections]]
name = "bridge"
...
```

```bash
score-to-song compose main_long.toml --out work/scores
score-to-song continue --source work/renders/first_song_main_s20261025 --keep-s 30.5 \
  --request work/scores/req_first_song_long_s20261025.json --out work/renders/first_song_long_s20261025
```

Before running, `continue` checks that every bar starting before `keep-s` is identical in both scores
(both voices, chords included). Choose `keep-s` inside a held note or a rest just before the new
material. A continuation can itself be continued.

## 4. More voices — `[derive]`, `render`, `separate`

YuE2 sings one solo voice per render. For a second voice, write another score with **the same tempo,
key, chords and accompaniment**, render it, and keep only its voice. A `[derive]` score does the
bookkeeping: it copies everything from the main score and transforms the melody (here one octave lower,
holding while the main voice moves, silent in section 2):

```toml
id = "first_song_low"
style = "Warm natural male solo voice ..."
[derive]
from = "main.toml"
transpose = -12
hold_shorter_than = 6
rest_sections = [2]
```

You can also write the second voice by hand (an answer in the gaps of the main line, a descant over its
last phrase): any score with the same sections and chords will do.

```bash
score-to-song separate work/renders/first_song_main_s20261025 work/renders/first_song_low_s20261025 --out work/voices
```

`separate` runs BS-RoFormer (via audio-separator) and writes `<render>_voice_estimate.wav` at 48 kHz.
Keep the **main voice as a native render** with its own accompaniment; add only the *voice estimates*
of the other renders, otherwise you stack two or three accompaniments. The main voice's estimate is
still useful as a level reference.

## 5. Mix — `mix`

A recipe lists the main track (one render, or several spliced at given times), the layers and their
gains:

```toml
output = "work/first_song_mix.wav"
[[main]]
file = "work/renders/first_song_main_s20261025/generate/audio.flac"
[[main]]
file = "work/renders/first_song_long_s20261025/generate/audio.flac"
at = 30.0                      # crossfade of 0.2 s ending at 30.0 s, before keep-s (30.5)
[[layers]]
file = "work/voices/first_song_low_s20261025_voice_estimate.wav"
windows = [[18.5, 31.4]]       # heard only there, 0.15 s fades
level = { match = "work/voices/first_song_main_s20261025_voice_estimate.wav", offset_lu = -4 }
[loop_test]
crossfade = 0.5
```

```bash
score-to-song mix mix.toml
```

The splice is refused if the two tracks do not agree in the crossfade (correlation under 0.8): that
catches a wrong `at` or a continuation of another render. A layer's level is either a fixed `gain_db`
or matched to a reference voice (`offset_lu = -4`: 4 loudness units below it). The mix is refused if it
peaks above −1 dBFS. `mix.wav.json` records every input with its SHA-256 and every setting; the same
recipe and inputs give the same bytes.

Full format: [mix-recipe.md](mix-recipe.md).

## 6. Listen and decide — `listen`

```bash
score-to-song listen "before=work/renders/first_song_main_s20261025/generate/audio.flac" \
  "after=work/first_song_mix.wav" "loop=work/first_song_mix_loop_test.wav" --out work/listen_1
open work/listen_1/index.html
```

Every copy is brought to −20 LUFS by a single linear gain (lowered for all if one would clip), so the
louder version does not win by default. Listen at one fixed volume. Measurements (pitch, timing) help to
find a defect; they do not tell you whether it sounds good — in our production, versions that measured
closer to the target were rejected by ear, and the reverse.

## Making something else

| You want | Change |
|---|---|
| another melody | the `melody` lines; keep one chord per bar and `|` checks to catch mistakes |
| another harmony | `chords` (native qualities: `m`, `7`, `maj7`, `sus4`, `dim`, `/bass`…) |
| another sound | `style` (voice and instruments), `[accompaniment] pattern` (`ostinato`, `drone`, `rest`) or explicit `ins` bars |
| another tempo or metre | `tempo`, `meter` (`3/4`, `6/8`…; bar length follows) |
| a longer piece | an `[extend]` score + `continue`, then splice in the recipe |
| a second or third voice | a `[derive]` score or a hand-written one, `render`, `separate`, a `[[layers]]` entry |
| a loop for a game | `length` + `[loop_test]`, and end the score on material that leads back to the start |
| a version for delivery | `format = "pcm24"` in the recipe |

Work in small steps: change one thing, render two or three seeds, listen, keep the best, continue from
it. Keep every render: the provenance files let you rebuild any version later.
