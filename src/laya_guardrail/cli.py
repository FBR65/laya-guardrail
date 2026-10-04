"""Kommandozeile: Pruefung eines Texts ohne HTTP-Server.

Beispiele:

    laya-guardrail --text "Wie koche ich Spaghetti?"
    laya-guardrail --file brief.txt --json
    echo "Text" | laya-guardrail

Der Exit-Code ist 0 bei PASS und 1 bei BLOCK, damit sich das Werkzeug in Pipes
und Skripten verwenden laesst.
"""
import argparse
import json
import sys

from .config import DEFAULT_ENDPOINT, DEFAULT_MODE, DEFAULT_MODEL, MAX_CONCURRENCY
from .core import guard


def build_parser():
    parser = argparse.ArgumentParser(
        prog="laya-guardrail",
        description="Prueft einen Text gegen die Laya-Guardrail (R1 bis R4)")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="zu pruefender Text")
    source.add_argument("--file", help="Datei mit dem zu pruefenden Text")
    parser.add_argument("--mode", default=DEFAULT_MODE,
                        choices=("sentences", "whole", "both"))
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=MAX_CONCURRENCY)
    parser.add_argument("--json", action="store_true",
                        help="maschinenlesbare Ausgabe")
    parser.add_argument("--fail-open", action="store_true",
                        help="bei Fehler PASS statt BLOCK (Standard: BLOCK)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.text is not None:
        text = args.text
    elif args.file:
        with open(args.file, encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("leere Eingabe", file=sys.stderr)
        return 2

    try:
        result = guard(text, mode=args.mode, fail_open=args.fail_open,
                       endpoint=args.endpoint, model=args.model,
                       timeout=args.timeout, workers=args.workers)
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["decision"].upper())
        if result.get("languages"):
            for entry in result["languages"]:
                print(f"  Sprache Satz {entry['sentence']}: {entry['lang']}"
                      f" (Konfidenz {entry['confidence']})")
        for reason in result["reasons"]:
            print("  - " + reason)

    return 1 if result["decision"] == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
