# Score files

A score file is TOML. `score-to-song compose` turns it into YuE2's native ABC and one request per seed.

## Top-level fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | name of the score; requests are `<id>_s<seed>`, the ABC is `<id>.abc` |
| `tempo` | yes | quarter notes per minute (`Q:1/4=`) |
| `key` | yes | `C`, `G`, `Bb`, `F#`, `Am`, `Dm`, `C#m`… (`K:`). Every accidental is written anyway |
| `style` | yes | the description sent to YuE2: voice, instruments, mood, what to avoid, tempo, key. English. No artist names, titles or recordings |
| `meter` | no | `4/4` (default), `3/4`, `6/8`… |
| `unit` | no | note unit `1/unit` (default 16: durations count sixteenths) |
| `seeds` | no | list; one request per seed (default `[1]`) |
| `cot` | no | YuE2 mode: `full` (default) sings melody and harmony from the score; `melody` uses a chord-free score |
| `naturals` | no | `always` (default) writes `=` on every natural note; `when-needed` only where the key or an earlier accidental in the bar would alter it. Sharps and flats are always written |
| `title` | no | `T:` field (empty by default) |
| `abc_file` | no | file name of the ABC (default `<id>.abc`) |
| `request_file` | no | file name of the requests, with `{seed}` (default `req_<id>_s{seed}.json`) |
| `[accompaniment]` | no | `pattern` (`ostinato`, `drone`, `rest`), `rhythm` (ostinato durations, default `[6, 6, 4]` in 4/4), `bars` (chord → explicit Ins bar) |

In TOML, keys written after a `[table]` header belong to that table: put the top-level fields first.

## Sections

```toml
[[sections]]
name = "chorus"                                   # intro, verse, chorus, bridge, outro, interlude, inst, pre-chorus, solo
chords = ["F", "G", "Am", "Am"]                   # one per bar: the number of bars of the section
melody = "C5:4 E5:4 A5:8 | G5:6 F5:2 D5:8 | C5:8 B4:4 A4:4~ | A4:12 r:4"
lyrics = ["Ah ah eh ah"]                          # lines sung in this section (none: played, not sung)
pattern = "drone"                                 # optional: overrides [accompaniment] pattern
ins = ["F,16", "G,16", "A,,16", "A,,16"]          # optional: explicit Ins bars (native ABC, without '|')
naturals = "when-needed"                          # optional: overrides the top-level setting
```

### Melody tokens

| Token | Meaning |
|---|---|
| `A4:8` | A above middle C (MIDI 69) for 8 units (a half note when unit = 16). Octaves are scientific: `C4` = middle C |
| `Bb4:2`, `C#5:4`, `F##3:4`, `Bn4:4` | flat, sharp, double sharp, explicit natural. Pitches are absolute: `B4` is always B natural, whatever the key |
| `r:16` | rest |
| `D5:16~` | tied to the next note, which must have the same pitch (also across sections) |
| `|` | bar check: fails if it does not fall on a barline |

A melody shorter than the section is completed with rests; a longer one is an error. Notes are split at
barlines (with ties) and into the lengths the dialect supports (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48).

### Chords

Native qualities only: major (no suffix), `m`, `dim`, `aug`, `7`, `maj7`, `m7`, `dim7`, `m7b5`, `sus4`,
`sus2`, `6`, `m6`, `7sus4`, `m(maj7)`, with an optional slash bass: `Eb/D`, `Gm/D`, `F#m7/C#`.

### Generated accompaniment (`Ins` voice)

| Pattern | Bar |
|---|---|
| `ostinato` | bass (slash bass or root, between A2 and G#3), the chord's fifth at least a fourth above, then the root above it; rhythm 6-6-4 sixteenths (3+3+2 eighths) |
| `drone` | the bass held for the whole bar |
| `rest` | silence |

The `Ins` line guides the accompaniment YuE2 generates; the `style` text decides the instruments. For
full control write the bars yourself (`ins`, or `[accompaniment.bars]` per chord).

## Derived scores — `[derive]`

```toml
id = "first_song_low"
style = "Warm natural male solo voice ..."
[derive]
from = "main.toml"
transpose = -12          # semitones
hold_shorter_than = 6    # notes shorter than this are absorbed into the sung note before them
rest_sections = [2]      # 1-based section numbers left silent (their lyrics too)
```

Copies tempo, key, sections, chords and accompaniment from `from`; top-level `style`, `seeds`, `cot`,
`naturals` override. A `[lyrics]` table (`"3" = ["Oh"]`) replaces the lyric lines of a section.

## Extended scores — `[extend]`

```toml
id = "first_song_long"
[extend]
from = "main.toml"
[[sections]]
name = "bridge"
...
```

All sections of `from`, unchanged, followed by the new ones: the score a continuation needs. Tempo,
metre, key and unit are those of `from`.

## From native ABC — `import-abc`

```bash
score-to-song import-abc score.abc --request req.json --out score.toml
```

Reads a native two-voice ABC (and the request, for style, seed and lyrics) and writes a score file with
the `Ins` bars kept as written. The command composes the result again and only keeps it if the ABC and
the lyrics come out identical. Chord changes inside a bar, tuplets, grace notes and repeats are not
supported.

## Notes from practice

- YuE2 does not always sing the written octave. In our renders, female voice descriptions sang one
  octave **below** the written pitch; we wrote a high second voice an octave above what we wanted to hear.
  Render, listen, adjust.
- The lines that were kept in our production used long held notes joined by half-steps, open vowels,
  and few, short rests.
- Try several seeds before rewriting the score: the same score sings quite differently from one seed to
  the next.
