"""Auswertung: ein Satz, ein Satzblock, ein ganzer Text.

Aufteilung der Regeln:

    R1  jailbreak, prompt_injection   je Satz
    R2  sensitive_data                je Satz
    R3  harm_severity                 je Block aus R3_GROUP_SIZE Saetzen
    R4  Sprache                       je Satz, ohne Laya

R3 laeuft nicht je Satz: satzweise hebt harm_severity harmlose Saetze ueber die
Schwelle (gemessen bis 2.55, waehrend harmlose Bloecke bei 2.01 bis 2.30 und die
Brandsatz-Anleitung bei 2.44 bis 2.45 liegen). Bloecke verduennen dafuer einen
einzelnen gefaehrlichen Satz unter harmlosen (gemessen: ein Gewaltsatz unter
neun harmlosen deutschen Saetzen ergibt 1.92).

Ein blockender Satz oder Block blockt den gesamten Text.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import language
from .client import QUESTIONS, QUESTIONS_R3, ask_laya
from .config import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODE,
    DEFAULT_MODEL,
    LANG_TARGET,
    MAX_CONCURRENCY,
    R3_GROUP_SIZE,
    THRESH_HARM,
    THRESH_INJECTION,
    THRESH_NOUL,
    VALID_MODES,
)
from .rules import rule_reasons
from .sentences import split_sentences

# Ein gemeinsamer Platzbegrenzer fuer alle Aufrufe an Laya, nicht je
# HTTP-Aufruf. Sonst ergaebe "gleichzeitige Anfragen mal workers" mehr als der
# llama-swap-Deckel erlaubt, und es kaeme HTTP 429.
_laya_slots = threading.BoundedSemaphore(MAX_CONCURRENCY)


def _language_of(sentence):
    """Sprache eines Satzes als (code, konfidenz, gruende).

    Die Spracherkennung darf einen Lauf nie stoppen: schlaegt sie fehl, bleibt
    der Code None und es gibt keinen Grund.
    """
    if not sentence.strip():
        return None, None, []
    try:
        code, confidence, is_target = language.detect(sentence)
    except Exception:  # noqa: BLE001 - absichtlich breit, siehe Docstring
        return None, None, []
    if code and not is_target:
        reasons = [
            f"R4 Sprache={code} (erwartet {LANG_TARGET}, Konfidenz {confidence:.3f})"
        ]
        return code, confidence, reasons
    return code, confidence, []


def check_one(sentence, endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, timeout=60.0):
    """Prueft einen Satz: R1, R2 und die Sprache. R3 wird nicht angewandt.

    Rueckgabe ist ein dict mit dem Urteil. Der harm_severity-Wert des Satzes
    wird mitgeliefert, aber erst auf Blockebene ausgewertet.
    """
    lang, lang_confidence, reasons = _language_of(sentence)

    try:
        with _laya_slots:
            response = ask_laya(sentence, endpoint, model, timeout,
                                questions=QUESTIONS)
    except Exception as exc:  # noqa: BLE001 - Fehler wird als Wert zurueckgegeben
        result = {"text": sentence,
                  "error": f"{type(exc).__name__}: {exc}"}
        if lang is not None:
            result["lang"] = lang
            result["lang_confidence"] = lang_confidence
        if reasons:
            result["decision"] = "block"
            result["reasons"] = reasons
        return result

    answers = response["answers"]
    values = {
        "jailbreak": answers["jailbreak"]["noul"],
        "prompt_injection": answers["prompt_injection"]["noul"],
        "sensitive_data": answers["sensitive_data"]["noul"],
        "harm_severity": answers["harm_severity"]["score"],
    }

    # R1 und R2 ohne R3: harm_severity wird hier nur berichtet.
    reasons = list(reasons) + rule_reasons(
        values["jailbreak"], values["prompt_injection"],
        values["sensitive_data"], -1.0)

    return {
        "text": sentence,
        "decision": "block" if reasons else "pass",
        "reasons": reasons,
        "values": values,
        "lang": lang,
        "lang_confidence": lang_confidence,
        "latency_ms": response.get("usage", {}).get("latency_ms"),
    }


def check_group(lines, endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, timeout=60.0):
    """Prueft einen Block von bis zu R3_GROUP_SIZE Saetzen als einen Text (R3).

    Rueckgabe: (harm_severity, grund, fehler, latenz_ms). harm_severity und
    grund sind None, wenn die Abfrage fehlschlug.
    """
    try:
        with _laya_slots:
            response = ask_laya(" ".join(lines), endpoint, model, timeout,
                                questions=QUESTIONS_R3)
    except Exception as exc:  # noqa: BLE001
        return None, None, f"{type(exc).__name__}: {exc}", None

    harm = response["answers"]["harm_severity"]["score"]
    reason = None
    if harm >= THRESH_HARM:
        reason = f"R3 harm_severity={harm:.2f} >= {THRESH_HARM:.1f}"
    return harm, reason, None, response.get("usage", {}).get("latency_ms")


def _r3_blocks(lines, endpoint, model, timeout, workers):
    """Bildet die Bloecke und wertet sie nebenlaeufig aus."""
    blocks = [lines[i:i + R3_GROUP_SIZE] for i in range(0, len(lines), R3_GROUP_SIZE)]
    if not blocks:
        return []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(
            lambda block: check_group(block, endpoint, model, timeout), blocks))

    groups = []
    for index, (block, outcome) in enumerate(zip(blocks, results, strict=True)):
        harm, reason, error, latency = outcome
        groups.append({
            "first_sentence": index * R3_GROUP_SIZE,
            "last_sentence": index * R3_GROUP_SIZE + len(block) - 1,
            "sentences": len(block),
            "text": " ".join(block),
            "harm_severity": harm,
            "decision": "block" if reason else "pass",
            "reasons": [reason] if reason else [],
            "error": error,
            "latency_ms": latency,
        })
    return groups


def guard(text, mode=DEFAULT_MODE, fail_open=False,
          endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, timeout=60.0,
          workers=MAX_CONCURRENCY):
    """Prueft einen Text und gibt das Gesamturteil zurueck.

    mode:
        "sentences"  je Satz pruefen (Standard)
        "whole"      den Gesamttext als einen Prompt pruefen; ausdruecklich
                     anzufordern, weil Laya auf mehrsaetzigen Texten fast
                     immer anschlaegt
        "both"       beides

    fail_open False (Standard) bedeutet: ein Fehler in einer Anfrage fuehrt zu
    BLOCK. True bedeutet: ein Fehler fuehrt zu PASS.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode muss {', '.join(VALID_MODES)} sein")

    # Die API nimmt beliebig viele Saetze an; an Laya gehen hoechstens
    # MAX_CONCURRENCY Anfragen gleichzeitig.
    workers = max(1, min(int(workers), MAX_CONCURRENCY))
    started = time.monotonic()

    result = {
        "mode": mode,
        "thresholds": {
            "jailbreak": THRESH_NOUL,
            "prompt_injection": THRESH_INJECTION,
            "sensitive_data": THRESH_NOUL,
            "harm": THRESH_HARM,
        },
        "workers": workers,
    }

    sentences = []
    if mode in ("sentences", "both"):
        parts = split_sentences(text)
        if parts:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                sentences = list(pool.map(
                    lambda sentence: check_one(sentence, endpoint, model, timeout),
                    parts))
        result["sentences"] = sentences
        result["r3_group_size"] = R3_GROUP_SIZE
        result["r3_blocks"] = []

    whole = None
    if mode in ("whole", "both") and text.strip():
        whole = check_one(text, endpoint, model, timeout)
        result["whole"] = whole
    elif mode == "whole" and not text.strip():
        whole = {"text": "", "error": "leere Eingabe"}
        result["whole"] = whole

    if mode == "whole":
        r3_lines = [text]
    else:
        r3_lines = [item["text"] for item in sentences if "text" in item]
    groups = _r3_blocks(r3_lines, endpoint, model, timeout, workers)
    if mode in ("sentences", "both"):
        result["r3_blocks"] = groups

    errors = [item for item in sentences if "error" in item]
    errors += [group for group in groups if group.get("error")]
    if whole and "error" in whole:
        errors.append(whole)

    blocked = [index for index, item in enumerate(sentences)
               if item.get("decision") == "block"]
    reasons = []
    for index in blocked[:20]:
        for reason in sentences[index].get("reasons", []):
            reasons.append(f"Satz {index}: {reason}")
    if whole:
        for reason in whole.get("reasons", []):
            reasons.append("Gesamttext: " + reason)
    for group in groups:
        for reason in group.get("reasons", []):
            reasons.append(f"Block Saetze {group['first_sentence']}-"
                           f"{group['last_sentence']}: {reason}")

    # Sprachen aller Saetze, die nicht in der Zielsprache sind.
    result["languages"] = [
        {"sentence": index, "lang": item.get("lang"),
         "confidence": item.get("lang_confidence")}
        for index, item in enumerate(sentences)
        if item.get("lang") and item.get("lang") != LANG_TARGET
    ]
    result["lang_target"] = LANG_TARGET

    if errors:
        if fail_open:
            result["decision"] = "pass"
            reasons = []
        else:
            result["decision"] = "block"
            reasons = [f"Fehler bei {len(errors)} Anfrage(n): {errors[0]['error']}"]
    elif reasons:
        result["decision"] = "block"
    else:
        result["decision"] = "pass"

    # Ein blockender Satz oder R3-Block blockt den gesamten Text.
    result["blocked_sentences"] = blocked
    result["blocked_r3_blocks"] = [index for index, group in enumerate(groups)
                                   if group.get("decision") == "block"]
    result["reasons"] = reasons
    result["fail_open"] = fail_open
    result["latency_ms"] = round((time.monotonic() - started) * 1000, 1)
    return result
