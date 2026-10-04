"""Tests der Satzzerlegung.

Diese Tests laufen ohne Laya und ohne Netz: sie pruefen ausschliesslich die
Zerlegung, die gemessen den Unterschied zwischen Fehlalarm und sauberem
Durchlauf macht.
"""
import pytest

from laya_guardrail.sentences import split_sentences


@pytest.mark.parametrize("text, expected", [
    # Abkuerzungen halten zusammen.
    ("Die Lieferzeit beträgt ca. 4 Wochen bzw. 6 Wochen ab Werk.",
     ["Die Lieferzeit beträgt ca. 4 Wochen bzw. 6 Wochen ab Werk."]),
    ("Unser Partner, z. B. die Firma Meier GmbH, übernimmt die Montage.",
     ["Unser Partner, z. B. die Firma Meier GmbH, übernimmt die Montage."]),
    ("Sehr geehrter Herr Dr. Berger, wir freuen uns sehr über Ihre Zusage.",
     ["Sehr geehrter Herr Dr. Berger, wir freuen uns sehr über Ihre Zusage."]),
    # Ordnungszahlen halten zusammen.
    ("vielen Dank für Ihre Anfrage vom 28. September zu unserer Beleuchtung.",
     ["vielen Dank für Ihre Anfrage vom 28. September zu unserer Beleuchtung."]),
    ("Bitte senden Sie uns die Unterlagen bis zum 10. Oktober zurück.",
     ["Bitte senden Sie uns die Unterlagen bis zum 10. Oktober zurück."]),
    # Tausendertrennzeichen und Betraege sind kein Satzende.
    ("Der Gesamtpreis beträgt 12.480,00 Euro netto zuzüglich der Umsatzsteuer.",
     ["Der Gesamtpreis beträgt 12.480,00 Euro netto zuzüglich der Umsatzsteuer."]),
    # Echte Satzgrenzen werden erkannt.
    ("Der Gesamtpreis beträgt 12.480,00 Euro netto. Bitte prüfen Sie die Angaben.",
     ["Der Gesamtpreis beträgt 12.480,00 Euro netto.",
      "Bitte prüfen Sie die Angaben."]),
    ("Wie hoch ist der Preis für die Anlage? Bitte nennen Sie uns die Konditionen.",
     ["Wie hoch ist der Preis für die Anlage?",
      "Bitte nennen Sie uns die Konditionen."]),
    # Kurze Stuecke werden nicht abgetrennt.
    ("Danke. Bitte senden Sie uns die unterschriebene Auftragsbestätigung zurück.",
     ["Danke. Bitte senden Sie uns die unterschriebene Auftragsbestätigung zurück."]),
    # Zeilenumbrueche trennen immer.
    ("Erste Zeile ohne Punkt\nZweite Zeile ohne Punkt",
     ["Erste Zeile ohne Punkt", "Zweite Zeile ohne Punkt"]),
])
def test_split_sentences(text, expected):
    assert split_sentences(text) == expected


def test_split_brief():
    """Der Geschaeftsbrief wird ohne falsche Trennungen zerlegt.

    Die grobe Trennung erzeugte hier 16 Saetze, darunter das Bruchstueck
    "vielen Dank für Ihre Anfrage vom 28." - das ueber R1 einen Fehlalarm
    ausloeste.
    """
    from pathlib import Path

    text = (Path(__file__).parent / "data" / "geschaeftsbrief.txt").read_text(encoding="utf-8")
    sentences = split_sentences(text)
    assert len(sentences) == 13
    # Kein Satz enthaelt mehr ein abgeschnittenes Datum.
    assert not any(s.endswith("vom 28.") for s in sentences)
    assert any("28. September" in s for s in sentences)
    assert any("10. Oktober" in s for s in sentences)
