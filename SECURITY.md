# Security policy

score-to-song runs locally and needs no account, key or network access once installed. It does run external
programs (mlx-Yue, ffmpeg, audio-separator) on files you pass to it, and it reads recipe and score files.

If you find a security problem (for example a recipe or score file that makes the toolkit write outside the
folders it names, or run a command), please **do not open a public issue**. Report it privately through
[GitHub's private vulnerability reporting](https://github.com/maoxor/score-to-song/security/advisories/new).

Problems in mlx-Yue, YuE2, audio-separator or ffmpeg themselves belong to those projects.
