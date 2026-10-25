"""Score file (TOML) -> native YuE2 ABC + one request JSON per seed. See docs/score-format.md.

A score describes sections; each section has one chord per bar, an optional melody line, optional lyric
lines and an accompaniment (generated pattern or explicit Ins bars). A score can also be derived from
another one ([derive]): same sections, chords and accompaniment, melody transposed and simplified, e.g. a
second voice doubling the main line an octave lower on its held notes.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import abc
from .abc import Event

SECTION_TAGS = {"intro", "verse", "chorus", "bridge", "outro", "interlude", "inst", "pre-chorus", "solo"}


@dataclass
class Section:
    name: str
    chords: list[str]
    melody: list[Event]
    lyrics: list[str]
    pattern: str
    ins: list[str] | None = None
    naturals: str | None = None   # overrides the score's setting for this section's melody


@dataclass
class Score:
    id: str
    tempo: int
    meter: str
    key: str
    unit: int
    naturals: str
    style: str
    seeds: list[int]
    cot: str
    sections: list[Section]
    title: str = ""
    abc_file: str | None = None
    accompaniment: dict = field(default_factory=dict)

    @property
    def bar_units(self) -> int:
        num, den = (int(x) for x in self.meter.split("/"))
        units = num * self.unit // den
        if units * den != num * self.unit:
            raise ValueError(f"meter {self.meter} does not fit a whole number of 1/{self.unit} units")
        return units


def _load(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_score(path: Path) -> Score:
    path = Path(path)
    data = _load(path)
    if "derive" in data:
        return _derive(path, data)
    if "extend" in data:
        return _extend(path, data)
    unknown = set(data) - {"id", "title", "tempo", "meter", "key", "unit", "naturals", "style", "seeds", "cot",
                           "abc_file", "accompaniment", "sections"}
    if unknown:
        raise ValueError(f"{path}: unknown fields {sorted(unknown)}")
    for required in ("id", "tempo", "key", "style", "sections"):
        if required not in data:
            raise ValueError(f"{path}: missing '{required}'")
    acc = data.get("accompaniment", {})
    score = Score(id=data["id"], title=data.get("title", ""), tempo=int(data["tempo"]), meter=data.get("meter", "4/4"),
                  key=data["key"], unit=int(data.get("unit", 16)), naturals=data.get("naturals", "always"),
                  style=data["style"].strip(), seeds=[int(s) for s in data.get("seeds", [1])], cot=data.get("cot", "full"),
                  sections=[], abc_file=data.get("abc_file"), accompaniment=acc)
    score.sections = _parse_sections(data.get("sections", []), score, acc)
    return score


def _parse_sections(raw: list[dict], score: Score, acc: dict) -> list[Section]:
    out = []
    for k, sec in enumerate(raw):
        name = sec.get("name", "")
        if name not in SECTION_TAGS:
            raise ValueError(f"section {k + 1}: name must be one of {sorted(SECTION_TAGS)}")
        chords = sec.get("chords", [])
        if not chords:
            raise ValueError(f"section {k + 1} ({name}): 'chords' must list one chord per bar")
        for c in chords:
            abc.parse_chord(c)
        ins = sec.get("ins")
        if ins is not None and len(ins) != len(chords):
            raise ValueError(f"section {k + 1} ({name}): {len(ins)} 'ins' bars for {len(chords)} chords")
        try:
            melody = abc.parse_melody(sec.get("melody", ""), score.bar_units)
        except ValueError as e:
            raise ValueError(f"section {k + 1} ({name}): {e}") from None
        unknown = set(sec) - {"name", "chords", "melody", "lyrics", "pattern", "ins", "naturals"}
        if unknown:
            raise ValueError(f"section {k + 1} ({name}): unknown fields {sorted(unknown)}")
        out.append(Section(name, chords, melody, list(sec.get("lyrics", [])),
                               sec.get("pattern", acc.get("pattern", "ostinato")), ins, sec.get("naturals")))
    return out


def _merge_ties(events: list[Event]) -> list[Event]:
    out: list[Event] = []
    for e in events:
        if out and out[-1].tie and e.pitch is not None and out[-1].pitch.midi == e.pitch.midi:
            out[-1] = Event(out[-1].pitch, out[-1].units + e.units, e.tie)
        else:
            out.append(e)
    return out


def _transpose(p: abc.Pitch, semitones: int) -> abc.Pitch:
    return p if semitones == 0 else (abc.Pitch(p.letter, p.alter, p.octave + semitones // 12) if semitones % 12 == 0
                                     else abc.pitch_from_midi(p.midi + semitones))


def derive_line(events: list[Event], transpose: int, hold_shorter_than: int) -> list[Event]:
    """Transpose a line; notes shorter than hold_shorter_than units are absorbed into the sung note before
    them, so the derived voice holds while the source moves."""
    out: list[Event] = []
    for e in _merge_ties(events):
        if e.pitch is not None and e.units < hold_shorter_than and out and out[-1].pitch is not None:
            out[-1] = Event(out[-1].pitch, out[-1].units + e.units, e.tie)
        else:
            out.append(Event(None if e.pitch is None else _transpose(e.pitch, transpose), e.units, e.tie))
    return out


def _derive(path: Path, data: dict) -> Score:
    d = data["derive"]
    if "id" not in data:
        raise ValueError(f"{path}: missing top-level 'id' (in TOML, put id, style and seeds before the [derive] table)")
    unknown = set(d) - {"from", "transpose", "hold_shorter_than", "rest_sections"}
    if unknown:
        raise ValueError(f"{path}: unknown [derive] fields {sorted(unknown)} (top-level fields go before [derive])")
    src = load_score(path.parent / d["from"])
    rest = set(d.get("rest_sections", []))
    sections = []
    for k, s in enumerate(src.sections, start=1):
        melody = ([Event(None, sum(e.units for e in s.melody))] if s.melody else []) if k in rest else \
            derive_line(s.melody, int(d.get("transpose", 0)), int(d.get("hold_shorter_than", 0)))
        lyrics = [] if k in rest else s.lyrics
        sections.append(Section(s.name, s.chords, melody, lyrics, s.pattern, s.ins, s.naturals))
    for k, lines in data.get("lyrics", {}).items():
        sections[int(k) - 1].lyrics = list(lines)
    return Score(id=data["id"], title=data.get("title", src.title), tempo=src.tempo, meter=src.meter, key=src.key,
                 unit=src.unit, naturals=data.get("naturals", src.naturals), style=data.get("style", src.style).strip(),
                 seeds=[int(s) for s in data.get("seeds", src.seeds)], cot=data.get("cot", src.cot), sections=sections,
                 abc_file=data.get("abc_file"), accompaniment=src.accompaniment)


def _extend(path: Path, data: dict) -> Score:
    """A continuation score: every section of another score, unchanged, followed by new sections. The
    continuation then repeats the source note for note up to its keep point, as it must."""
    if "id" not in data:
        raise ValueError(f"{path}: missing top-level 'id' (in TOML, put id, style and seeds before the [extend] table)")
    e = data["extend"]
    if set(e) - {"from"}:
        raise ValueError(f"{path}: [extend] takes only 'from' (top-level fields go before [extend])")
    src = load_score(path.parent / e["from"])
    unknown = set(data) - {"id", "title", "style", "seeds", "cot", "naturals", "abc_file", "sections", "extend"}
    if unknown:
        raise ValueError(f"{path}: unknown fields {sorted(unknown)} (an extension keeps the source's tempo, meter, key and unit)")
    score = Score(id=data["id"], title=data.get("title", src.title), tempo=src.tempo, meter=src.meter, key=src.key, unit=src.unit,
                  naturals=data.get("naturals", src.naturals), style=data.get("style", src.style).strip(),
                  seeds=[int(x) for x in data.get("seeds", src.seeds)], cot=data.get("cot", src.cot), sections=[],
                  abc_file=data.get("abc_file"), accompaniment=src.accompaniment)
    score.sections = src.sections + _parse_sections(data.get("sections", []), score, src.accompaniment)
    return score


def ins_bar(score: Score, section: Section, k: int) -> str:
    if section.ins is not None:
        return section.ins[k]
    chord = section.chords[k]
    explicit = score.accompaniment.get("bars", {})
    if chord in explicit and section.pattern != "rest":
        return explicit[chord]
    events = abc.accompaniment_bar(chord, section.pattern, score.bar_units, score.accompaniment.get("rhythm"))
    return abc.bar_text(events, score.key, score.naturals)


def to_abc(score: Score) -> str:
    lines = ["X:1", f"T:{score.title}", f"M:{score.meter}", f"L:1/{score.unit}", f"Q:1/4={score.tempo}",
             'V: Vocal clef=treble name="Vocal Melody" snm="Vocal"', 'V: Ins clef=treble name="Ins Melody" snm="Inst."',
             f"K:{score.key}"]
    all_bars = []
    for s in score.sections:
        try:
            all_bars.append(abc.pack(s.melody, score.bar_units, len(s.chords)))
        except ValueError as e:
            raise ValueError(f"section {s.name!r}: {e}") from None
    abc.check_ties([b for bars in all_bars for b in bars])
    for s, bars in zip(score.sections, all_bars):
        for g in range(0, len(s.chords), 4):
            idx = range(g, min(g + 4, len(s.chords)))
            vocal = "".join(f'"{s.chords[i]}"{abc.bar_text(bars[i], score.key, s.naturals or score.naturals)}|' for i in idx)
            ins = "".join(ins_bar(score, s, i) + "|" for i in idx)
            lines += [f"% {s.name}", "V: Vocal", vocal, "V: Ins", ins]
    return "\n".join(lines) + "\n"


def lyrics_text(score: Score) -> str:
    return "\n\n".join("\n".join([f"[{s.name.title()}]", *s.lyrics]) for s in score.sections)


def nominal_seconds(score: Score) -> float:
    return sum(len(s.chords) for s in score.sections) * score.bar_units * 4 / score.unit * 60 / score.tempo


def requests(score: Score, abc_name: str) -> list[dict]:
    return [{"id": f"{score.id}_s{seed}", "style": score.style, "lyrics": lyrics_text(score), "cot": score.cot,
             "seed": seed, "abc_path": abc_name} for seed in score.seeds]


def _write(path: Path, text: str, force: bool) -> str:
    if path.exists() and path.read_text(encoding="utf-8") != text and not force:
        raise SystemExit(f"{path} exists with different content; use --force to replace it")
    state = "unchanged" if path.exists() and path.read_text(encoding="utf-8") == text else "written"
    path.write_text(text, encoding="utf-8")
    return state


def compose(score_path: Path, out_dir: Path, force: bool = False) -> dict:
    score = load_score(score_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    abc_name = score.abc_file or f"{score.id}.abc"
    report = {"score": str(score_path), "abc": str(out_dir / abc_name),
              "abc_state": _write(out_dir / abc_name, to_abc(score), force),
              "bars": sum(len(s.chords) for s in score.sections), "nominal_seconds": round(nominal_seconds(score), 2),
              "requests": []}
    for req in requests(score, abc_name):
        p = out_dir / f"req_{req['id']}.json"
        state = _write(p, json.dumps(req, ensure_ascii=False, indent=1) + "\n", force)
        report["requests"].append({"path": str(p), "state": state})
    return report
