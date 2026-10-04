"""Tests der Regeln R1 bis R3.

Reine Rechenpruefung ohne Laya und ohne Netz.
"""
import pytest

from laya_guardrail.config import THRESH_HARM, THRESH_INJECTION, THRESH_NOUL
from laya_guardrail.rules import rule_reasons, verdict


def test_thresholds_are_the_agreed_values():
    assert (THRESH_NOUL, THRESH_INJECTION, THRESH_HARM) == (0.5, 0.9, 2.3)


def test_harmless_text_passes():
    reasons = rule_reasons(jailbreak=0.001, prompt_injection=0.002,
                           sensitive_data=0.001, harm_severity=1.01)
    assert reasons == []


@pytest.mark.parametrize("values, expected_rule", [
    # R1: jailbreak ueber 0.5
    ((0.997, 0.002, 0.001, 1.50), "R1 jailbreak"),
    # R1: prompt_injection ueber 0.9 (der Fehlalarm lag bei 0.749)
    ((0.010, 0.995, 0.001, 1.50), "R1 prompt_injection"),
    # R2: sensitive_data ueber 0.5
    ((0.010, 0.002, 0.972, 1.50), "R2 sensitive_data"),
    # R3: harm_severity ab 2.3
    ((0.010, 0.002, 0.001, 2.45), "R3 harm_severity"),
])
def test_each_rule_fires(values, expected_rule):
    reasons = rule_reasons(*values)
    assert any(reason.startswith(expected_rule) for reason in reasons), reasons


def test_injection_0749_does_not_fire():
    """Der gemessene Fehlalarm auf einem sauberen Geschaeftssatz darf nicht
    mehr ausloesen; die Schwelle liegt bei 0.9."""
    reasons = rule_reasons(jailbreak=0.099, prompt_injection=0.7491,
                           sensitive_data=0.002, harm_severity=2.10)
    assert reasons == []


def test_harm_just_below_threshold_passes():
    assert rule_reasons(0.0, 0.0, 0.0, 2.29) == []
    assert rule_reasons(0.0, 0.0, 0.0, 2.30) != []


def test_verdict_reads_laya_answer():
    answers = {
        "jailbreak": {"noul": 0.998},
        "prompt_injection": {"noul": 0.997},
        "sensitive_data": {"noul": 0.031},
        "harm_severity": {"score": 1.65},
    }
    block, reasons, values = verdict(answers)
    assert block is True
    assert values["jailbreak"] == 0.998
    assert any("R1 jailbreak" in reason for reason in reasons)
