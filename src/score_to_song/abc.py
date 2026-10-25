"""Write the bounded ABC dialect that YuE2 reads natively (two monophonic voices, Vocal and Ins).

Pitches are spelled as written by the user (Bb4 stays a flat B, A#4 a sharp A). Durations are integer
numbers of the score unit (L:1/16 by default). A note longer than the space left in its bar is split at
the barline and tied; a duration the dialect cannot write in one token (5, 7, 10...) is split into
supported lengths and tied. Accidentals are always explicit, so the key signature never changes a pitch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

SUPPORTED = [48, 32, 24, 16, 12, 8, 6, 4, 3, 2, 1]   # duration multipliers of the native dialect
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_ORDER, FLAT_ORDER = "FCGDAEB", "BEADGCF"
MAJOR_SHARPS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
                "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
RELATIVE_MAJOR = {"Am": "C", "Em": "G", "Bm": "D", "F#m": "A", "C#m": "E", "G#m": "B", "D#m": "F#", "A#m": "C#",
                  "Dm": "F", "Gm": "Bb", "Cm": "Eb", "Fm": "Ab", "Bbm": "Db", "Ebm": "Gb", "Abm": "Cb"}
CHORD_QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8), "7": (0, 4, 7, 10),
                   "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10), "dim7": (0, 3, 6, 9), "m7b5": (0, 3, 6, 10),
                   "sus4": (0, 5, 7), "sus2": (0, 2, 7), "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9),
                   "7sus4": (0, 5, 7, 10), "m(maj7)": (0, 3, 7, 11)}
NOTE_RE = re.compile(r"^([A-Ga-g])(##|bb|#|b|n)?(-?\d)$")
CHORD_RE = re.compile(r"^([A-G])(#|b)?(.*?)(?:/([A-G])(#|b)?)?$")


@dataclass(frozen=True)
class Pitch:
    letter: str   # C..B
    alter: int    # -2..2
    octave: int   # scientific octave: C4 = middle C = MIDI 60

    @property
    def midi(self) -> int:
        return 12 * (self.octave + 1) + LETTER_PC[self.letter] + self.alter


@dataclass(frozen=True)
class Event:
    pitch: Pitch | None   # None = rest
    units: int
    tie: bool = False     # tied to the next event (same pitch required)


def parse_pitch(text: str) -> Pitch:
    """'D4', 'Bb4', 'C#5', 'F##3', 'Bn4' (explicit natural). C4 = MIDI 60."""
    m = NOTE_RE.match(text)
    if not m:
        raise ValueError(f"not a pitch: {text!r} (expected e.g. D4, Bb4, C#5)")
    alter = {"": 0, None: 0, "n": 0, "#": 1, "##": 2, "b": -1, "bb": -2}[m.group(2)]
    return Pitch(m.group(1).upper(), alter, int(m.group(3)))


def parse_melody(text: str, bar_units: int | None = None) -> list[Event]:
    """Space-separated tokens PITCH:UNITS ('A4:8', 'r:16' for a rest); a trailing '~' ties the note to the
    next one, which must have the same pitch (also across sections). '|' is an optional bar check: it must
    fall on a barline (counted from the start of the section)."""
    events, pos = [], 0
    for token in text.split():
        if token == "|":
            if bar_units and pos % bar_units:
                raise ValueError(f"bar check '|' at unit {pos}, not on a barline (bar = {bar_units} units)")
            continue
        tie = token.endswith("~")
        body = token[:-1] if tie else token
        if ":" not in body:
            raise ValueError(f"token {token!r}: expected PITCH:UNITS")
        name, units = body.rsplit(":", 1)
        if not units.isdigit() or int(units) <= 0:
            raise ValueError(f"token {token!r}: duration must be a positive whole number of units")
        pitch = None if name in ("r", "z", "-") else parse_pitch(name)
        if pitch is None and tie:
            raise ValueError(f"token {token!r}: a rest cannot be tied")
        events.append(Event(pitch, int(units), tie))
        pos += int(units)
    return events


def split_units(n: int) -> list[int]:
    out = []
    for s in SUPPORTED:
        while n >= s:
            out.append(s)
            n -= s
    return out


def pack(events: list[Event], bar_units: int, n_bars: int | None = None) -> list[list[Event]]:
    """Cut a continuous line into bars; notes are split at barlines and into supported lengths, with ties.
    The last bar is completed with rests; with n_bars, the line is padded (or rejected if longer)."""
    bars, cur, filled = [], [], 0
    for ev in events:
        units = ev.units
        while units > 0:
            take = min(units, bar_units - filled)
            pieces = split_units(take)
            for k, p in enumerate(pieces):
                last = k == len(pieces) - 1 and units - take == 0
                cur.append(Event(ev.pitch, p, ev.pitch is not None and (not last or ev.tie)))
            units -= take
            filled += take
            if filled == bar_units:
                bars.append(cur)
                cur, filled = [], 0
    if cur:
        cur += [Event(None, u) for u in split_units(bar_units - filled)]
        bars.append(cur)
    if n_bars is not None:
        if len(bars) > n_bars:
            raise ValueError(f"melody lasts {len(bars)} bars, the section has {n_bars} chords (one per bar)")
        bars += [[Event(None, u) for u in split_units(bar_units)] for _ in range(n_bars - len(bars))]
    return bars


def check_ties(bars: list[list[Event]]) -> None:
    flat = [e for bar in bars for e in bar]
    for a, b in zip(flat, flat[1:]):
        if a.tie and (b.pitch is None or b.pitch.midi != a.pitch.midi):
            raise ValueError(f"tie from {a.pitch} must reach the same pitch (next is {b.pitch})")
    if flat and flat[-1].tie:
        raise ValueError("the line ends on an unresolved tie")


def key_alterations(key: str) -> dict[str, int]:
    """Letters altered by the key signature, e.g. Dm -> {'B': -1}."""
    major = RELATIVE_MAJOR.get(key, key)
    if major not in MAJOR_SHARPS:
        raise ValueError(f"unsupported key {key!r} (use a major or minor key such as D, Bb, F#m, Dm)")
    n = MAJOR_SHARPS[major]
    return {ch: 1 for ch in SHARP_ORDER[:n]} if n >= 0 else {ch: -1 for ch in FLAT_ORDER[:-n]}


class BarSpeller:
    """Spell one bar. Sharps and flats are always written. naturals='always' also writes '=' on every
    natural note; 'when-needed' writes '=' only when the key signature or an earlier accidental of that
    letter in the bar would otherwise alter it. Native convention: an accidental applies to its letter in
    every octave until the barline."""

    def __init__(self, key: str, naturals: str = "always"):
        if naturals not in ("always", "when-needed"):
            raise ValueError("naturals must be 'always' or 'when-needed'")
        self.signature, self.naturals = key_alterations(key), naturals
        self.state: dict[str, int] = {}

    def note(self, p: Pitch) -> str:
        current = self.state.get(p.letter, self.signature.get(p.letter, 0))
        sign = {-2: "__", -1: "_", 1: "^", 2: "^^"}.get(p.alter, "")
        if p.alter == 0:
            sign = "=" if self.naturals == "always" or current != 0 else ""
        self.state[p.letter] = p.alter
        if p.octave >= 5:
            return sign + p.letter.lower() + "'" * (p.octave - 5)
        return sign + p.letter + "," * (4 - p.octave)


def bar_text(bar: list[Event], key: str, naturals: str = "always") -> str:
    speller = BarSpeller(key, naturals)
    return "".join(("z" if e.pitch is None else speller.note(e.pitch)) + str(e.units) + ("-" if e.tie else "")
                   for e in bar)


def parse_chord(symbol: str) -> tuple[int, tuple[int, ...], int]:
    """'Dm' -> (2, (0, 3, 7), 2); 'Eb/D' -> (3, (0, 4, 7), 2). Returns root pc, intervals, bass pc."""
    m = CHORD_RE.match(symbol)
    if not m or m.group(3) not in CHORD_QUALITIES:
        raise ValueError(f"unsupported chord {symbol!r}; qualities: {', '.join(q or 'major' for q in CHORD_QUALITIES)}")
    acc = {"#": 1, "b": -1, None: 0}
    root = (LETTER_PC[m.group(1)] + acc[m.group(2)]) % 12
    bass = (LETTER_PC[m.group(4)] + acc[m.group(5)]) % 12 if m.group(4) else root
    return root, CHORD_QUALITIES[m.group(3)], bass


PC_SPELLING = {0: ("C", 0), 1: ("C", 1), 2: ("D", 0), 3: ("E", -1), 4: ("E", 0), 5: ("F", 0), 6: ("F", 1),
               7: ("G", 0), 8: ("A", -1), 9: ("A", 0), 10: ("B", -1), 11: ("B", 0)}


def pitch_from_midi(midi: int) -> Pitch:
    letter, alter = PC_SPELLING[midi % 12]
    return Pitch(letter, alter, (midi - LETTER_PC[letter] - alter) // 12 - 1)


def accompaniment_bar(chord: str, pattern: str, bar_units: int, rhythm: list[int] | None = None) -> list[Event]:
    """Generated Ins bar. 'drone': the bass note held for the bar. 'ostinato': bass, chord fifth, chord root
    climbing (rhythm 6-6-4 in 4/4, i.e. 3+3+2 eighths). 'rest': silence. The bass (slash bass or root) sits
    in the octave from A2 to G#3."""
    root, intervals, bass_pc = parse_chord(chord)
    bass = 45 + (bass_pc - 9) % 12
    if pattern == "rest":
        return [Event(None, u) for u in split_units(bar_units)]
    if pattern == "drone":
        return [Event(pitch_from_midi(bass), u, k < len(split_units(bar_units)) - 1)
                for k, u in enumerate(split_units(bar_units))]
    if pattern != "ostinato":
        raise ValueError(f"unknown accompaniment pattern {pattern!r} (ostinato, drone, rest, or explicit 'ins' bars)")
    rhythm = rhythm or ([6, 6, 4] if bar_units == 16 else [bar_units // 2, bar_units - bar_units // 2])
    if sum(rhythm) != bar_units or any(u not in SUPPORTED for u in rhythm):
        raise ValueError(f"ostinato rhythm {rhythm} must use supported lengths and fill a bar of {bar_units}")
    fifth = bass + 5 + (root + intervals[2 if len(intervals) > 2 else -1] - bass - 5) % 12   # at least a fourth above the bass
    top = fifth + 1 + (root - fifth - 1) % 12                                                # next root above
    notes = [bass, fifth, top, fifth]
    return [Event(pitch_from_midi(notes[k % len(notes)]), u) for k, u in enumerate(rhythm)]


# --- reading native ABC back (for continuation checks) ---

def bars_by_voice(text: str) -> dict[str, list[str]]:
    """Bars of each voice of a native ABC text, in order, as written (chord symbols included)."""
    out: dict[str, list[str]] = {"Vocal": [], "Ins": []}
    lines = text.splitlines()
    for k, line in enumerate(lines):
        name = line.split(":", 1)[1].strip() if line.startswith("V:") else None
        if name in out and k + 1 < len(lines) and not lines[k + 1].startswith(("V:", "%")):
            out[name] += [b for b in lines[k + 1].split("|") if b.strip()]
    return out


def header_field(text: str, field: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(field + ":"):
            return line[len(field) + 1:].strip()
    return None


def bar_seconds(text: str) -> float:
    """Duration of one bar from the M: and Q:1/4= fields."""
    num, den = (int(x) for x in header_field(text, "M").split("/"))
    q = header_field(text, "Q")
    bpm = Fraction(q.split("=")[1]) if q and "=" in q else Fraction(120)
    return float(Fraction(num * 4, den) * 60 / bpm)


TOKEN_RE = re.compile(r'"([^"]*)"|(\^\^|__|\^|_|=)?([A-Ga-g])([\',]*)(\d*)(-?)|([zZ])(\d*)|(\s+)')


def parse_bar(text: str, key: str, bar_units: int) -> tuple[str | None, list[Event]]:
    """Read one bar of the native dialect: an optional leading chord symbol, then notes and rests.
    Returns (chord, events) with pitches resolved through the key signature and the bar's accidentals."""
    signature, state = key_alterations(key), {}
    chord, events, pos = None, [], 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            raise ValueError(f"unsupported ABC in bar {text!r} at {text[pos:pos + 8]!r}")
        pos = m.end()
        if m.group(1) is not None:
            if events or chord is not None:
                raise ValueError(f"chord change inside bar {text!r} is not supported by score files")
            chord = m.group(1)
        elif m.group(3):
            sign, letter, marks, digits, tie = m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
            up = letter.upper()
            if sign:
                state[up] = {"^^": 2, "^": 1, "=": 0, "_": -1, "__": -2}[sign]
            octave = (5 if letter.islower() else 4) + marks.count("'") - marks.count(",")
            events.append(Event(Pitch(up, state.get(up, signature.get(up, 0)), octave), int(digits or 1), tie == "-"))
        elif m.group(7):
            n = int(m.group(8) or 1)
            events.append(Event(None, n * bar_units if m.group(7) == "Z" else n))
    return chord, events
