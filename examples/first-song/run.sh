#!/usr/bin/env bash
# The whole workflow on an original example: compose -> render -> continue -> separate -> mix -> listen.
# Needs the engines (scripts/install.sh) and 10-12 GB of free memory for each render. Steps already done
# are skipped, nothing is overwritten. Everything is written to work/ (ignored by Git).
set -euo pipefail
cd "$(dirname "$0")"
S=${SCORE_TO_SONG:-score-to-song}
SEED=20261025
R=work/renders

# 1. scores -> native ABC + requests
$S compose main.toml low.toml main_long.toml --out work/scores --force   # scores are rebuilt from the .toml files
# 2. render the main voice and the second voice (one solo voice per render)
$S render work/scores/req_first_song_main_s$SEED.json work/scores/req_first_song_low_s$SEED.json --out $R
# 3. continue the main render: keep its first 30.5 s, sing the bridge and the ending of main_long.toml
[[ -d $R/first_song_long_s$SEED ]] || $S continue --source $R/first_song_main_s$SEED --keep-s 30.5 \
  --request work/scores/req_first_song_long_s$SEED.json --out $R/first_song_long_s$SEED
# 4. voice estimates: the second voice (to lay it in) and the main voice (level reference)
$S separate $R/first_song_main_s$SEED $R/first_song_low_s$SEED --out work/voices
# 5. mix, then a listening page with every file at the same loudness
[[ -f work/first_song_mix.wav ]] || $S mix mix.toml
$S listen "main render=$R/first_song_main_s$SEED/generate/audio.flac" "continuation=$R/first_song_long_s$SEED/generate/audio.flac" \
  "mix=work/first_song_mix.wav" "loop point=work/first_song_mix_loop_test.wav" --out "work/listen_$(date +%Y%m%d-%H%M%S)" --title "first-song"
