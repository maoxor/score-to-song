# Changelog

All notable changes to score-to-song. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/). Mix arithmetic changes are always listed, because
they change the output of existing recipes.

## [0.1.1] - 2026-10-25

### Fixed
- `render` no longer skips a request whose earlier render failed: it stops and points to the log. The failed
  folder is kept for diagnosis; move it away to render again.
- `separate` reuses an existing estimate only if its sidecar shows it was made from the same input file;
  otherwise it stops instead of silently keeping an estimate of another render.
- Provenance (`tool.commit`) no longer records the commit of an unrelated Git work tree when score-to-song is
  installed inside one (for example a `.venv` in a project folder).
- A failing external command (`ffmpeg`) is reported as an error message instead of a Python traceback.
- `scripts/install.sh --help` printed one line of code after the usage text.

### Added
- Tests for the command line, the render and separation guards and the listening page (21 tests).
- Continuous integration on Python 3.11, 3.12 and 3.13, plus lint (ruff, ShellCheck).
- Changelog, security policy, issue and pull request templates.

Mix arithmetic is unchanged: recipes give bit-identical WAV files.

## [0.1.0] - 2026-10-25

First public release: `compose`, `import-abc`, `render`, `continue`, `separate`, `mix`, `listen`, `doctor`,
the `first-song` example and the documentation.

[0.1.1]: https://github.com/maoxor/score-to-song/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/maoxor/score-to-song/releases/tag/v0.1.0
