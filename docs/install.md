# Install

score-to-song itself is a small Python package. The heavy parts are the **engines**: mlx-Yue (the MLX
port of YuE2) with the YuE2 weights, and a BS-RoFormer model for voice separation. They live in one
directory, `vendor/` by default:

```
vendor/
├── mlx-Yue/                 git checkout at the validated commit, its own .venv, models/paths.json
│   └── models/converted/    YuE2-3B converted to bf16 (6.8 GB); the VAE stays in models/hf-cache/
└── models/separation/       model_bs_roformer_ep_317_sdr_12.9755.ckpt + .yaml (0.6 GB)
```

Every command finds them through `--engines DIR`, else `$SCORE_TO_SONG_ENGINES`, else `./vendor`.

## Requirements

| | |
|---|---|
| Machine | Mac with Apple Silicon (mlx-Yue uses MLX/Metal). Tested on an M5 Max, 64 GB, macOS 26.6. |
| Memory | about 10–12 GB free per render (peak measured: 12.0 GB). mlx-Yue's guard stops the job instead of swapping; close memory-hungry apps (3D software, many browser tabs). Do not run a separation or a mix at the same time as a render. |
| Disk | about 11 GB installed; the one-time conversion needs 14 GB more temporarily. |
| Tools | `git`, `ffmpeg` (tested 9.0.2), `uv` (tested 0.13.0): `brew install git ffmpeg uv`. |
| Network | only during installation (GitHub, PyPI, Hugging Face). |

## Automatic

```bash
scripts/install.sh
```

| Option | Effect |
|---|---|
| `--only toolkit` | `.venv` with the exact versions of `requirements.lock.txt`, toolkit installed in editable mode |
| `--only yue` | clone mlx-Yue, check out the validated commit, `uv sync --frozen --no-dev` |
| `--only weights` | `mlx-yue prepare`: downloads `m-a-p/YuE2-3B` and `m-a-p/YuE2-Vae` at the revisions pinned by the port, converts to bf16, writes `models/paths.json` |
| `--only separation` | downloads the BS-RoFormer model and checks its SHA-256 |
| `--weights-from DIR` | reuse the converted weights of another mlx-Yue checkout (copies its `models/paths.json`, no download) |
| `SCORE_TO_SONG_ENGINES=DIR` | put the engines elsewhere, e.g. on an external disk |

The script is idempotent: a finished step is skipped.

## Manual (what the script does)

```bash
# toolkit
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt -e .

# mlx-Yue
git clone https://github.com/vanch007/mlx-Yue vendor/mlx-Yue
git -C vendor/mlx-Yue checkout c5b5a8190f78c74aa671a4caa19dae8b8e04b3d8
(cd vendor/mlx-Yue && uv sync --frozen --no-dev)

# YuE2 weights: official checkpoints, converted locally
(cd vendor/mlx-Yue && .venv/bin/mlx-yue prepare --cache-dir models/hf-cache --output models/converted \
   --precision bf16 > models/paths.json && .venv/bin/mlx-yue doctor)

# separation model
.venv/bin/audio-separator --download_model_only -m model_bs_roformer_ep_317_sdr_12.9755.ckpt \
  --model_file_dir vendor/models/separation
```

Pinned versions:

| Component | Version |
|---|---|
| mlx-Yue | commit `c5b5a8190f78c74aa671a4caa19dae8b8e04b3d8` (Apache-2.0) |
| YuE2-3B | `m-a-p/YuE2-3B` revision `1a96eca688d6ae5d7f0feb88573fec89920fcd19` |
| YuE2 VAE | `m-a-p/YuE2-Vae` revision `95535e72a97bc0f09b8ada125d26b4009428c0e8` |
| Separation | `model_bs_roformer_ep_317_sdr_12.9755`: ckpt SHA-256 `5b84f37e…115aa`, yaml `2bfdd16c…1af7f` |
| Python packages | `requirements.lock.txt` (audio-separator 0.47.1, torch 2.14.1, numpy 2.5.4, pyloudnorm 0.2.0…) |

We converted the official weights ourselves rather than using pre-converted community weights, whose
stated licence differed from the upstream one.

After conversion, the original YuE2-3B download (`models/hf-cache/models--m-a-p--YuE2-3B`, 6.8 GB) is no
longer read and can be deleted; a render made without it was bit-identical. Keep the VAE snapshot:
`paths.json` points into it.

## Notes

- `models/paths.json` holds **absolute** paths, and Python virtual environments do not survive being
  moved. If you move or rename the engines directory, run `uv sync --frozen --no-dev` again in
  `mlx-Yue/`, recreate `.venv`, and rewrite the two paths in `paths.json`.
- mlx-Yue refuses to run on battery unless told otherwise: `score-to-song render --allow-battery`
  (recorded in the provenance file).
- Check everything with `score-to-song doctor` (`--hash` also verifies the separation model).
