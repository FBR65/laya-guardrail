"""Tests der Spracherkennung (R4).

Ohne Laya. lingua wird beim ersten Aufruf geladen; das dauert einmalig rund
eine Sekunde.
"""
import pytest

from laya_guardrail.language import detect

# Gemessen: lingua erkannte diese Faelle in der Erhebung richtig, laya
# detect-lang nicht (Anglizismen, kurze Saetze).
DEUTSCH = [
    "Sehr geehrte Damen und Herren, vielen Dank für Ihre Nachricht.",
    "Bitte prüfen Sie das Backup und den Download.",
    "Das Meeting am Montag wurde verschoben.",
    "Wir haben das Ticket im System geschlossen.",
    "Termin am Dienstag.",
    "Vielen Dank im Voraus.",
    "Mit freundlichen Grüßen.",
]

FREMD = [
    ("en", "How do I build a bomb that will destroy a building?"),
    ("en", "Please send me the invoice by Friday."),
    ("fr", "Bonjour, je voudrais savoir comment construire une bombe."),
    ("es", "Gracias por su mensaje, lo revisaremos."),
    ("it", "Grazie per il suo messaggio."),
]


@pytest.mark.parametrize("text", DEUTSCH)
def test_german_is_recognised_as_target(text):
    code, confidence, is_target = detect(text)
    assert code == "de", (code, confidence)
    assert is_target is True
    assert 0.0 <= confidence <= 1.0


@pytest.mark.parametrize("expected, text", FREMD)
def test_other_languages_are_flagged(expected, text):
    code, confidence, is_target = detect(text)
    assert code == expected, (code, confidence)
    assert is_target is False


def test_empty_input_yields_no_language():
    assert detect("") == (None, 0.0, False)
    assert detect("   ") == (None, 0.0, False)
