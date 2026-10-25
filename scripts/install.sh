#!/usr/bin/env bash
# Install score-to-song and its engines on a Mac with Apple Silicon. Safe to re-run: finished steps are skipped.
#
#   scripts/install.sh                        everything: toolkit, mlx-Yue, YuE2 weights (~14 GB download), separation model
#   scripts/install.sh --only toolkit         one step: toolkit | yue | weights | separation
#   scripts/install.sh --weights-from DIR     reuse the converted weights of another mlx-Yue checkout (no download)
#   SCORE_TO_SONG_ENGINES=/big/disk/engines scripts/install.sh    engines elsewhere (default: ./vendor)
#
# Nothing is bought or uploaded. The YuE2 weights are downloaded from Hugging Face (m-a-p/YuE2-3B, m-a-p/YuE2-Vae)
# and converted locally; read their licence first (docs/rights.md).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
ENGINES=${SCORE_TO_SONG_ENGINES:-$ROOT/vendor}
YUE=$ENGINES/mlx-Yue
SEP=$ENGINES/models/separation
MLX_YUE_REPO=https://github.com/vanch007/mlx-Yue
MLX_YUE_COMMIT=c5b5a8190f78c74aa671a4caa19dae8b8e04b3d8
MODEL=model_bs_roformer_ep_317_sdr_12.9755
ONLY=""; WEIGHTS_FROM=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --only) ONLY=$2; shift 2 ;;
    --weights-from) WEIGHTS_FROM=$2; shift 2 ;;
    -h|--help) sed -n 2,11p "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
want() { [[ -z $ONLY || $ONLY == "$1" ]]; }
say() { printf '\n== %s\n' "$*"; }

[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo "mlx-Yue needs macOS on Apple Silicon" >&2; exit 1; }
for tool in git ffmpeg uv; do
  command -v $tool >/dev/null || { echo "$tool is missing: brew install git ffmpeg uv" >&2; exit 1; }
done
mkdir -p "$ENGINES"

if want toolkit; then
  say "toolkit: .venv (Python 3.12) with the validated versions (requirements.lock.txt)"
  [[ -x .venv/bin/python ]] || uv venv --python 3.12 .venv
  uv pip install --python .venv/bin/python -r requirements.lock.txt -e .
fi

if want yue; then
  say "mlx-Yue at $MLX_YUE_COMMIT in $YUE"
  [[ -d $YUE/.git ]] || git clone "$MLX_YUE_REPO" "$YUE"
  git -C "$YUE" checkout --quiet "$MLX_YUE_COMMIT"
  (cd "$YUE" && uv sync --frozen --no-dev)
fi

if want weights; then
  if [[ -f $YUE/models/paths.json ]]; then
    say "weights: $YUE/models/paths.json exists, kept"
  elif [[ -n $WEIGHTS_FROM ]]; then
    say "weights: reusing $WEIGHTS_FROM/models"
    mkdir -p "$YUE/models"
    cp "$WEIGHTS_FROM/models/paths.json" "$YUE/models/paths.json"
  else
    say "weights: download m-a-p/YuE2-3B and m-a-p/YuE2-Vae, convert to bf16 locally (about 14 GB, then 7.3 GB kept)"
    (cd "$YUE" && .venv/bin/mlx-yue prepare --cache-dir models/hf-cache --output models/converted --precision bf16 > models/paths.json.tmp \
      && mv models/paths.json.tmp models/paths.json)
    echo "The original YuE2-3B download ($YUE/models/hf-cache/models--m-a-p--YuE2-3B, 6.8 GB) is no longer read after"
    echo "conversion and may be deleted to save space; keep the VAE snapshot, which paths.json points to."
  fi
  (cd "$YUE" && .venv/bin/mlx-yue doctor) || echo "mlx-yue doctor reported a problem (see above)"
fi

if want separation; then
  say "separation model $MODEL in $SEP"
  mkdir -p "$SEP"
  [[ -f $SEP/$MODEL.ckpt ]] || .venv/bin/audio-separator --download_model_only -m "$MODEL.ckpt" --model_file_dir "$SEP"
  shasum -a 256 -c <<EOF
5b84f37e8d444c8cb30c79d77f613a41c05868ff9c9ac6c7049c00aefae115aa  $SEP/$MODEL.ckpt
2bfdd16c656bd9519aba757cc4f8834b7ede675eb1e00ec4772d74ae1c41af7f  $SEP/$MODEL.yaml
EOF
fi

say "check"
SCORE_TO_SONG_ENGINES=$ENGINES .venv/bin/score-to-song doctor || true
echo
echo "Activate with: source .venv/bin/activate   (engines: $ENGINES; set SCORE_TO_SONG_ENGINES if not ./vendor)"
