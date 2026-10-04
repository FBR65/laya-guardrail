"""Spracherkennung je Satz mit lingua-language-detector.

Warum lingua und nicht laya detect-lang: gemessen an 18 harten Faellen (kurze
Saetze, Anglizismen, fremdsprachige Einschuebe) lag lingua bei 16 von 18
Treffern, laya detect-lang bei 13 von 18. Die Fehler von laya detect-lang
treffen genau die Faelle aus dem Geschaeftsverkehr: "Das Meeting am Montag
wurde verschoben." und "Termin am Dienstag." galten als englisch. lingua
braucht rund 0.3 ms je Satz.

Die Erkennung ist nicht fehlerfrei. Bei kurzen Bruchstuecken sinkt die
Konfidenz auf 0.3 bis 0.6, und deutsche Saetze mit englischen Fachwoertern
oder Einschueben koennen als englisch gelten (gemessen: "Der Report enthaelt
ein Update zum Deployment." mit Konfidenz 0.487, noch als deutsch erkannt).
Die Konfidenz wird darum immer mitgeliefert.
"""
from lingua import Language, LanguageDetectorBuilder

# Sprachen, zwischen denen unterschieden wird. Deutsch ist die Zielsprache.
# Hinweis: lingua benennt Norwegisch als BOKMAL und NYNORSK.
LANGUAGES = (
    Language.GERMAN, Language.ENGLISH, Language.FRENCH, Language.SPANISH,
    Language.ITALIAN, Language.PORTUGUESE, Language.DUTCH, Language.POLISH,
    Language.CZECH, Language.SLOVAK, Language.DANISH, Language.SWEDISH,
    Language.BOKMAL, Language.NYNORSK, Language.FINNISH, Language.HUNGARIAN,
    Language.ROMANIAN, Language.BULGARIAN, Language.CROATIAN,
    Language.SLOVENE, Language.SERBIAN, Language.BOSNIAN, Language.ESTONIAN,
    Language.LATVIAN, Language.LITHUANIAN, Language.GREEK, Language.RUSSIAN,
    Language.UKRAINIAN, Language.BELARUSIAN, Language.TURKISH,
    Language.ARABIC, Language.HEBREW, Language.PERSIAN, Language.HINDI,
    Language.BENGALI, Language.URDU, Language.TAMIL, Language.TELUGU,
    Language.MARATHI, Language.GUJARATI, Language.PUNJABI, Language.THAI,
    Language.VIETNAMESE, Language.INDONESIAN, Language.MALAY, Language.TAGALOG,
    Language.CHINESE, Language.JAPANESE, Language.KOREAN, Language.SWAHILI,
)

_detector = None


def _get_detector():
    """Baut den Detektor beim ersten Gebrauch. Der Modellaufbau dauert
    einmalig rund eine Sekunde, danach kostet ein Satz 0.3 ms."""
    global _detector
    if _detector is None:
        _detector = LanguageDetectorBuilder.from_languages(*LANGUAGES).build()
    return _detector


def detect(text):
    """Bestimmt die Sprache eines Texts.

    Rueckgabe: (iso639_1, konfidenz, ist_deutsch).

    iso639_1 ist der zweibuchstabige Sprachcode ("de", "en", "fr"), oder None,
    wenn keine Sprache bestimmt werden konnte (reine Zahlen, Satzzeichen).
    Die Konfidenz liegt zwischen 0.0 und 1.0.
    """
    if not text or not text.strip():
        return None, 0.0, False
    detector = _get_detector()
    language = detector.detect_language_of(text)
    if language is None:
        return None, 0.0, False
    confidence = round(detector.compute_language_confidence(text, language), 4)
    iso = language.iso_code_639_1.name.lower()
    return iso, confidence, iso == "de"
