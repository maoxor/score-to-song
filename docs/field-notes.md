# Field notes

What we learned producing a 1 min 56 s three-voice wordless piece with this workflow (October 2026,
mlx-Yue `c5b5a81`, YuE2-3B bf16, M5 Max 64 GB). They are observations on our material, not general
truths about YuE2. Each is marked: **measured** (a number we computed), **heard** (a listening decision
by the person directing the music) or **documented** (from the model's or a tool's documentation).

## Scores

- **Octave.** Female voice descriptions sang our scores one octave **below** the written pitch, every
  time (measured: median sung pitch an octave under the score). We kept the main line as written (it
  gave a low, warm female voice, heard: approved) and wrote the high second voice one octave above the
  pitch we wanted.
- **Seeds matter more than wording.** For the high voice we rendered six seeds of the same request and
  kept one that sang 11 of 11 planned notes, about 0.1 s late, with 8–17 cents of vibrato (measured).
  Other seeds had an opera-like vibrato of 38–50 cents (measured) that was rejected (heard).
- **What YuE2 does not control.** Glides, breaths, swells and vibrato depth are not in the score. Asking
  for them in the style text helped little. Choose seeds; do not expect a score edit to fix them.
- **Wordless lyrics** (`Ah ah eh ah`, one line per phrase) worked for a voice used as an instrument.

## Extending a piece

- **A fresh render of a longer score does not keep the voice.** Four fresh renders of a developed version
  of an approved take reproduced the structure but not the voice: vibrato of 15–45 cents instead of 10,
  timbre distance 49–93 where two decodes of the same render differ by 45 (measured). They were discarded.
- **A continuation does.** With the source's tokens imposed up to the keep point, the kept part matched
  the source (correlation 0.90–0.98, about 1 dB difference, measured) and the new part kept the timbre
  (heard: approved). The final piece is the first render spliced at 43.5 s into a continuation of a
  continuation (correlation in the crossfade 0.956, measured).
- Splice a little **before** the keep point, inside a held note: the crossfade then joins two versions of
  the same sound.

## Several voices

- **One render per voice, then separation.** Asking for a duet in the style text, or giving the second
  verse to a male voice in one render, did not give a usable duet (measured: no voice detected in the
  first verse of one attempt). Rendering each voice from its own score, with the same tempo, chords,
  accompaniment and seed, then separating the extra voices and laying them under the main render, did
  (heard: "best result so far").
- **Keep the main voice native.** Only the extra voices are separation estimates; otherwise two or three
  accompaniments pile up. The estimates keep a little of their own accompaniment (heard and measured);
  present them as estimates, never as original stems.
- **Levels and timing.** Extra voices 4 LU under the main voice's estimate sat well (heard). Renders of
  scores sharing a tempo start nearly together: most delays were 0–0.3 s, up to 1.25 s for later parts of
  a continuation, set by ear. A take can also be reused elsewhere: one male phrase was laid again 68 s
  later for the final climax.
- **Roles per section** keep three voices clear: a voice answers in the gaps, holds under a moving line,
  or rests. Decide them in the scores, not in the mix.

## Mixing and listening

- Only linear gains and short fades (0.15–1 s). No reverb was added: in earlier attempts, echoes and long
  tails were what the listener objected to most (heard).
- Peaks were kept under −1 dBFS, and an earlier climax was lowered by 1 dB so the final one stays the
  highest (heard).
- **Measurements help find defects; they do not judge.** Versions that measured closer to the target
  were rejected by ear, and versions that measured worse were kept. Compare at equal loudness, decide by
  ear, write the decision down.

## Machine

- Peak memory of a render: 12.0 GB of physical footprint (11.2 GB in MLX) for a 129 s continuation;
  9.6 GB for a 49 s render (measured). mlx-Yue's guard stops a job as soon as the system starts swapping;
  a 3D application holding about 50 GB blocked renders twice. Run one heavy job at a time.
- Rendering the same request again on the same machine gave a **bit-identical** file (same tokens, same
  audio), even after deleting the original download of the weights (measured). Separation and mixing are
  also bit-identical when repeated (measured).

## What did not work for us

Before this workflow: synthesisers driven by code, and text-to-audio models without a score, produced
material that was rejected (heard: "arcade" sound, ghostly voices, no sung melody). Correcting vibrato
afterwards with pitch-shifting (PSOLA) reduced it but was not kept. A study that copied the gestures of a
reference recording closely was dropped: it is not original material.
