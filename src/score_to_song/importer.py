"""Native YuE2 ABC (+ optional request JSON) -> score file (TOML), so that an existing score can be edited
and recomposed with `score-to-song compose`. The Ins voice is kept bar by bar as written ('ins' lists).
Composing the imported file gives back the same ABC text; `import-abc` checks this before writing.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import abc
from .abc import Event

ALTER_TEXT = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}


def _token(e: Event) -> str:
    if e.pitch is None:
        return f"r:{e.units}"
    return f"{e.pitch.letter}{ALTER_TEXT[e.pitch.alter]}{e.pitch.octave}:{e.units}" + ("~" if e.tie else "")


def _groups(text: str) -> list[tuple[str, list[str], list[str]]]:
    lines, out, k = text.splitlines(), [], 0
    while k < len(lines):
        if lines[k].startswith("% "):
            name = lines[k][2:].strip()
            if lines[k + 1] != "V: Vocal" or lines[k + 3] != "V: Ins":
                raise ValueError(f"line {k + 1}: expected '% name', 'V: Vocal', bars, 'V: Ins', bars")
            vocal = [b for b in lines[k + 2].split("|") if b.strip()]
            ins = [b for b in lines[k + 4].split("|") if b.strip()]
            if len(vocal) != len(ins):
                raise ValueError(f"group {name!r} at line {k + 1}: {len(vocal)} Vocal bars, {len(ins)} Ins bars")
            out.append((name, vocal, ins))
            k += 5
        else:
            k += 1
    return out


def _lyric_blocks(lyrics: str) -> list[tuple[str, list[str]]]:
    blocks = []
    for chunk in lyrics.split("\n\n"):
        rows = chunk.split("\n")
        if not rows[0].startswith("["):
            raise ValueError(f"lyrics block without a [Section] tag: {chunk!r}")
        blocks.append((rows[0].strip("[]").lower(), [r for r in rows[1:] if r]))
    return blocks


def _sections(groups, blocks):
    """Assign ABC groups (<= 4 bars each) to lyric blocks. A run of groups with one name matches a run of
    blocks with that name: one block takes the whole run, or each block takes one group."""
    def runs(items, key):
        out = []
        for it in items:
            if out and key(out[-1][-1]) == key(it):
                out[-1].append(it)
            else:
                out.append([it])
        return out
    g_runs = runs(groups, lambda g: g[0])
    if blocks is None:
        return [(run, []) for run in g_runs]
    b_runs = runs(blocks, lambda b: b[0])
    if [r[0][0] for r in g_runs] != [r[0][0] for r in b_runs]:
        raise ValueError(f"section order differs between ABC {[r[0][0] for r in g_runs]} and lyrics {[r[0][0] for r in b_runs]}")
    out = []
    for gr, br in zip(g_runs, b_runs, strict=True):
        if len(br) == 1:
            out.append((gr, br[0][1]))
        elif len(br) == len(gr):
            out += [([g], b[1]) for g, b in zip(gr, br, strict=True)]
        else:
            raise ValueError(f"cannot split {len(gr)} '{gr[0][0]}' groups among {len(br)} lyric blocks")
    return out


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def import_abc(abc_text: str, request: dict | None = None, score_id: str | None = None, abc_file: str | None = None,
               request_file: str | None = None) -> str:
    key, meter = abc.header_field(abc_text, "K"), abc.header_field(abc_text, "M")
    unit = int(abc.header_field(abc_text, "L").split("/")[1])
    tempo = int(abc.header_field(abc_text, "Q").split("=")[1])
    num, den = (int(x) for x in meter.split("/"))
    bar_units = num * unit // den
    blocks = _lyric_blocks(request["lyrics"]) if request else None
    seed = request.get("seed") if request else None
    sid = score_id or (request["id"].rsplit("_s", 1)[0] if request and "_s" in request["id"] else "imported")
    out = ["# Imported from native ABC by score-to-song import-abc", f"id = {_q(sid)}"]
    title = abc.header_field(abc_text, "T") or ""
    if title:
        out.append(f"title = {_q(title)}")
    out += [f"tempo = {tempo}", f"meter = {_q(meter)}", f"key = {_q(key)}", f"unit = {unit}"]
    if abc_file:
        out.append(f"abc_file = {_q(abc_file)}")
    if request_file and seed is not None and f"_s{seed}" in request_file:
        # stored as a template ('req_x_s{seed}.json') so that compose writes the same request file name
        out.append(f"request_file = {_q(request_file.replace(f'_s{seed}', '_s{seed}'))}")
    if request:
        out += [f"seeds = [{seed}]", f"cot = {_q(request.get('cot', 'full'))}", f"style = {_q(request['style'])}"]
    else:
        out += ["seeds = [1]", 'style = ""   # fill in: describe voice and accompaniment (English, no artist names)']
    for run, lyrics in _sections(_groups(abc_text), blocks):
        chords, melody, ins, naturals = [], [], [], "when-needed"
        for _name, vocal, ins_bars in run:
            for bar in vocal:
                chord, events = abc.parse_bar(bar, key, bar_units)
                if chord is None:
                    raise ValueError(f"bar {bar!r} has no chord symbol; score files need one chord per bar")
                if "=" in bar:
                    naturals = "always"
                chords.append(chord)
                melody.append(" ".join(_token(e) for e in events))
            ins += ins_bars
        rests_only = all(t.startswith("r:") for bar in melody for t in bar.split())
        out += ["", "[[sections]]", f"name = {_q(run[0][0])}", f"chords = [{', '.join(_q(c) for c in chords)}]"]
        if not rests_only:
            out.append(f"melody = {_q(' | '.join(melody))}")
            out.append(f"naturals = {_q(naturals)}")
        if lyrics:
            out.append(f"lyrics = [{', '.join(_q(x) for x in lyrics)}]")
        out.append(f"ins = [{', '.join(_q(x) for x in ins)}]")
    return "\n".join(out) + "\n"


def import_files(abc_path: Path, request_path: Path | None, out_path: Path, score_id: str | None = None) -> dict:
    from .compose import load_score, lyrics_text, to_abc
    text = abc_path.read_text(encoding="utf-8")
    request = json.loads(request_path.read_text(encoding="utf-8")) if request_path else None
    if request and request.get("abc") and not request.get("abc_path"):
        raise ValueError("request carries inline ABC; pass that ABC as a file")
    toml_text = import_abc(text, request, score_id, abc_path.name, request_path.name if request_path else None)
    if out_path.exists():
        raise SystemExit(f"{out_path} exists; choose a new file name")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(toml_text, encoding="utf-8")
    score = load_score(out_path)
    same_abc = to_abc(score) == text
    same_lyrics = request is None or lyrics_text(score) == request["lyrics"]
    if not (same_abc and same_lyrics):
        out_path.unlink()
        raise SystemExit(f"round trip failed (abc identical: {same_abc}, lyrics identical: {same_lyrics}); nothing written")
    return {"score": str(out_path), "sections": len(score.sections), "round_trip": "identical ABC" + (" and lyrics" if request else "")}
