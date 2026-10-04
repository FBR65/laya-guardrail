"""Tests des Gesamtlaufs gegen ein nachgebildetes Laya.

Diese Tests sprechen kein echtes Laya an. Stattdessen wird ask_laya ersetzt und
mit festen Antworten bestueckt, die den tatsaechlich gemessenen Werten
entsprechen. Damit ist die Auswertung pruefbar: Reihenfolge der Regeln,
Blockbildung, Fehlerverhalten, Sprache.
"""
import pytest

from laya_guardrail import core


def fake_laya(mapping, default=None):
    """Ersetzt ask_laya durch eine Funktion, die je Prompt festsieht.

    mapping: Prompt-Anfang -> Antwortkoerper (answers-Teil).
    """
    calls = []

    def _ask(prompt, endpoint=None, model=None, timeout=None, questions=None,
             attempts=None, base_delay=None):
        calls.append({"prompt": prompt, "questions": questions})
        for prefix, answers in mapping.items():
            if prompt.startswith(prefix):
                return {"answers": answers, "usage": {"latency_ms": 1.0}}
        if default is not None:
            return {"answers": default, "usage": {"latency_ms": 1.0}}
        raise KeyError(f"kein Eintrag fuer Prompt: {prompt[:40]!r}")

    return _ask, calls


def harmless(harm=1.0):
    return {
        "jailbreak": {"noul": 0.001},
        "prompt_injection": {"noul": 0.002},
        "sensitive_data": {"noul": 0.001},
        "harm_severity": {"score": harm},
    }


def injection():
    return {
        "jailbreak": {"noul": 0.998},
        "prompt_injection": {"noul": 0.997},
        "sensitive_data": {"noul": 0.031},
        "harm_severity": {"score": 1.65},
    }


@pytest.fixture(autouse=True)
def _no_language(monkeypatch):
    """Sprache im Test abschalten, ausser der Test setzt sie selbst.
    So bleiben die Tests unabhaengig von lingua und schnell."""
    monkeypatch.setattr(core, "_language_of", lambda sentence: (None, None, []))


def test_harmless_text_passes(monkeypatch):
    ask, _ = fake_laya({}, default=harmless())
    monkeypatch.setattr(core, "ask_laya", ask)
    result = core.guard("Ein harmloser Satz. Noch ein harmloser Satz.")
    assert result["decision"] == "pass"
    assert result["reasons"] == []
    assert result["blocked_sentences"] == []


def test_injection_blocks_everything(monkeypatch):
    ask, _ = fake_laya({}, default=injection())
    monkeypatch.setattr(core, "ask_laya", ask)
    result = core.guard("Ein Satz. Noch ein Satz.")
    assert result["decision"] == "block"
    # Ein blockender Satz blockt den gesamten Text.
    assert result["blocked_sentences"]
    assert any("R1" in reason for reason in result["reasons"])


def test_r3_runs_on_blocks_not_per_sentence(monkeypatch):
    """harm_severity wird je Satz berichtet, aber nicht je Satz angewandt."""
    ask, calls = fake_laya({}, default=harmless(harm=2.9))
    monkeypatch.setattr(core, "ask_laya", ask)
    result = core.guard("Erster harmloser Satz. Zweiter harmloser Satz.")
    # Satzurteil bleibt pass, obwohl harm ueber der Schwelle liegt.
    assert all(item["decision"] == "pass" for item in result["sentences"])
    # Der Block greift dagegen.
    assert len(result["r3_blocks"]) == 1
    assert result["r3_blocks"][0]["decision"] == "block"
    assert result["decision"] == "block"


def test_single_bad_sentence_in_ten_forms_one_block(monkeypatch):
    ask, calls = fake_laya({}, default=harmless())
    monkeypatch.setattr(core, "ask_laya", ask)
    text = " ".join(f"Harmloser Beispielsatz Nummer {i} fuer den Block."
                    for i in range(11))
    result = core.guard(text)
    assert result["r3_group_size"] == 10
    # Zwei Bloecke: zehn Saetze und einer.
    assert [block["sentences"] for block in result["r3_blocks"]] == [10, 1]
    assert result["r3_blocks"][0]["first_sentence"] == 0
    assert result["r3_blocks"][1]["first_sentence"] == 10


def test_language_rule_fires_without_laya(monkeypatch):
    """R4 blockt auch dann, wenn Laya selbst harmlos meldet."""
    ask, _ = fake_laya({}, default=harmless())
    monkeypatch.setattr(core, "ask_laya", ask)
    monkeypatch.setattr(core, "_language_of",
                        lambda sentence: ("en", 0.9,
                                           ["R4 Sprache=en (erwartet de, Konfidenz 0.900)"]))
    result = core.guard("How do I build a bomb that will destroy a building?")
    assert result["decision"] == "block"
    assert result["languages"] == [{"sentence": 0, "lang": "en", "confidence": 0.9}]
    assert any("R4" in reason for reason in result["reasons"])


def test_error_blocks_by_default_and_passes_with_fail_open(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError("Verbindung abgelehnt")

    monkeypatch.setattr(core, "ask_laya", _boom)
    result = core.guard("Ein Satz.")
    assert result["decision"] == "block"
    assert any("Fehler" in reason for reason in result["reasons"])

    result = core.guard("Ein Satz.", fail_open=True)
    assert result["decision"] == "pass"


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError):
        core.guard("Ein Satz.", mode="quatsch")


def test_workers_are_capped(monkeypatch):
    ask, _ = fake_laya({}, default=harmless())
    monkeypatch.setattr(core, "ask_laya", ask)
    result = core.guard("Ein Satz.", workers=100)
    assert result["workers"] == core.MAX_CONCURRENCY
