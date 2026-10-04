"""Die Regeln R1 bis R3 und ihre Anwendung auf eine Laya-Antwort.

Die Regeln sind bewusst einfach gehalten: je Frage ein Schwellwert, jeder
Treffer blockt. R4 (Sprache) steht in der Auswertung, weil sie ohne Laya
entschieden wird.
"""
from .config import THRESH_HARM, THRESH_INJECTION, THRESH_NOUL


def rule_reasons(jailbreak, prompt_injection, sensitive_data, harm_severity):
    """Wendet R1 bis R3 auf vier Werte an.

    Rueckgabe: Liste der Gruende. Leer heisst: kein Treffer.
    """
    reasons = []
    if jailbreak > THRESH_NOUL:
        reasons.append(f"R1 jailbreak={jailbreak:.4f} > {THRESH_NOUL:.1f}")
    if prompt_injection > THRESH_INJECTION:
        reasons.append(
            f"R1 prompt_injection={prompt_injection:.4f} > {THRESH_INJECTION:.1f}"
        )
    if sensitive_data > THRESH_NOUL:
        reasons.append(f"R2 sensitive_data={sensitive_data:.4f} > {THRESH_NOUL:.1f}")
    if harm_severity >= THRESH_HARM:
        reasons.append(f"R3 harm_severity={harm_severity:.2f} >= {THRESH_HARM:.1f}")
    return reasons


def values(answers):
    """Zieht die vier Werte aus einer Laya-Antwort."""
    return {
        "jailbreak": answers["jailbreak"]["noul"],
        "prompt_injection": answers["prompt_injection"]["noul"],
        "sensitive_data": answers["sensitive_data"]["noul"],
        "harm_severity": answers["harm_severity"]["score"],
    }


def verdict(answers):
    """Wendet R1 bis R3 auf eine vollstaendige Laya-Antwort an.

    Rueckgabe: (block, gruende, werte).
    """
    v = values(answers)
    reasons = rule_reasons(v["jailbreak"], v["prompt_injection"],
                           v["sensitive_data"], v["harm_severity"])
    return bool(reasons), reasons, v
