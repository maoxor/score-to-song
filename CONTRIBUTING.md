# Contributing

Thank you for helping. Bug reports, examples, docs and code are welcome.

## Set up

```bash
scripts/install.sh --only toolkit      # .venv with the validated versions; enough for the tests
source .venv/bin/activate
uv pip install -e '.[dev]'             # pytest and ruff (the .venv made by uv has no pip of its own)
pytest                                 # unit tests: no model, no audio download, a few seconds
ruff check src tests                   # lint, as in CI
```

Changes to `render`, `continue` or `separate` also need the engines (`scripts/install.sh`) and a real
run: `examples/first-song/run.sh` exercises every command.

## Rules of the project

- **Never overwrite a result.** Every command refuses to replace an existing output. Keep it that way.
- **Record provenance.** A new output needs a JSON sidecar: inputs with SHA-256, settings, tool version,
  date. Keep keys and tokens out of files and logs (the toolkit needs none).
- **Deterministic files.** Write WAV through `wavio.write_wav` (no timestamped chunks).
- **No hidden processing.** The mix stage is linear gains, delays and fades. A new effect would be a new,
  explicit, opt-in feature, recorded in the sidecar.
- **Bit-exactness is a feature.** `mix` reproduces productions bit for bit from their recipes; if you
  change arithmetic in `mix.py` (order of operations, fades), say so in the pull request: it changes
  the output of existing recipes.
- **Original material only** in examples and tests: no excerpts of recordings, no artist names in
  prompts, no generated audio committed (audio files are ignored by Git).
- Docs describe what the code does today. If you change behaviour, change the docs in the same pull
  request.

## Pull requests

1. One topic per pull request, with a short description of what changes for a user.
2. `pytest` and `ruff check src tests` pass; add a test for a bug you fix.
3. Add a line to `CHANGELOG.md` under a new or `Unreleased` heading.
4. For anything that touches sound, say what you ran (machine, command) and what you heard or measured.

## Reporting a problem

Use the issue form: it asks for `score-to-song doctor` output, the command, and the `.log` or `.json` next
to the failed output. Do not attach audio you cannot share. Security problems: see [SECURITY.md](SECURITY.md).

## Licence

Contributions are accepted under the Apache License 2.0 (see [docs/rights.md](docs/rights.md)).
