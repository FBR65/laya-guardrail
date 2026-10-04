"""Satzzerlegung fuer die Guardrail.

Deutsche Geschaeftstexte enthalten Abkuerzungen ("bzw.", "z. B.", "Dr."),
Initialen ("H. Berger") und Ordnungszahlen ("28. September", "3. Quartal").
Eine Trennung an jedem Punkt mit folgendem Leerzeichen zerlegt solche Texte
falsch; die Bruchstuecke verschieben anschliessend die Laya-Werte.

Gemessen: die alte, grobe Trennung erzeugte aus einem Geschaeftsbrief
Fehlalarme ueber R1 (ein Bruchstueck erreichte prompt_injection = 0.749).
Mit dieser Trennung laeuft derselbe Brief ueber R1 und R2 sauber durch.
"""
import re

from .config import MIN_SENTENCE

# Zeilenumbrueche trennen immer (Listen, Log-Zeilen, Chat-Turns).
_LINE_BREAK = re.compile(r"\n+")

# Kandidat fuer ein Satzende: Satzzeichen, danach Leerraum und ein
# Nicht-Leerzeichen (Beginn des moeglichen naechsten Satzes).
_CANDIDATE = re.compile(r"(?<=[.!?\u2026])\s+(?=\S)")

# Abkuerzungen, nach denen der Punkt kein Satzende ist.
_ABBREV = {
    "z", "b", "d", "u", "a", "s", "vgl", "bzw", "ca", "etwa", "ggf", "evtl",
    "inkl", "zzgl", "max", "min", "abs", "art", "nr", "bzgl", "sog", "usw",
    "etc", "dr", "prof", "hr", "fr", "jr", "st", "bspw", "tel", "fax", "mrd",
    "mio", "tsd", "jh", "jhd", "allg", "bes", "gg", "zzt",
    "jan", "feb", "mrz", "apr", "jun", "jul", "aug", "sep", "sept", "okt",
    "nov", "dez",
}

# Das letzte Wort vor dem Punkt, samt Umlauten und scharfem S.
_WORD_BEFORE = re.compile(r"([A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df]+)\.$")


def _split_line(line):
    """Zerlegt eine Zeile an den Stellen, die sichere Satzenden sind."""
    out, start = [], 0
    for match in _CANDIDATE.finditer(line):
        cut = match.start()
        head = line[start:cut]
        if len(head) < MIN_SENTENCE:       # zu kurz fuer einen eigenen Satz
            continue

        word = _WORD_BEFORE.search(head)
        if word:
            token = word.group(1)
            if token.lower() in _ABBREV:   # "bzw." ist kein Satzende
                continue
            if len(token) == 1:            # Initiale, "H. Berger"
                continue

        if re.search(r"\d\.$", head):       # "28." oder "10."
            nxt = line[cut:cut + 12].strip()
            # Zahl, Punkt, Grossbuchstabe: Ordinalzahl ("10. Oktober"), kein
            # Satzende.
            if nxt and nxt[0].isupper():
                continue

        out.append(head.strip())
        start = match.end()

    rest = line[start:].strip()
    if rest:
        out.append(rest)
    return out or [line]


def split_sentences(text):
    """Trennt Text in Saetze.

    Zeilenumbrueche sind immer eine Trennung. Innerhalb einer Zeile wird nur
    an sicheren Satzenden getrennt: Abkuerzungen, Initialen und Ordnungszahlen
    halten zusammen. Stuecke unter MIN_SENTENCE Zeichen werden nicht
    abgetrennt, damit keine Bruchstuecke entstehen.
    """
    out = []
    for line in _LINE_BREAK.split(text):
        line = line.strip()
        if not line:
            continue
        out.extend(_split_line(line))
    return [sentence for sentence in out if sentence]
