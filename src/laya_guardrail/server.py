"""HTTP-Server der Guardrail.

Endpunkte:

    GET  /health   Zustand, angebundenes Laya und Zaehler
    POST /guard    Pruefung eines Texts; JSON oder reiner Text

Der Server nutzt nur die Standardbibliothek. Zwei Grenzen sind eingebaut und
begruendet:

* limit_concurrency begrenzt die gleichzeitig bearbeiteten HTTP-Anfragen.
  Darueber liegende Anfragen warten auf einen freien Platz, statt einen Fehler
  zu bekommen. Entspricht --limit-concurrency bei uvicorn.
* Ein gemeinsamer Platzbegrenzer im Kern begrenzt die Anfragen an Laya auf
  MAX_CONCURRENCY (siehe core). Beides ist noetig: ohne die zweite Grenze
  ergibt "gleichzeitige Anfragen mal workers" ein Vielfaches des
  llama-swap-Deckels und es kaeme HTTP 429.

Start:

    python -m laya_guardrail.server --port 8645
"""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .config import DEFAULT_ENDPOINT, DEFAULT_MODEL, MAX_CONCURRENCY
from .core import guard

DEFAULT_PORT = 8645
DEFAULT_HOST = "127.0.0.1"

# Standard fuer gleichzeitig bearbeitete HTTP-Anfragen.
DEFAULT_LIMIT_CONCURRENCY = 20


class Handler(BaseHTTPRequestHandler):
    """Behandelt /health und /guard. Die Laufzeitwerte stehen in args."""

    args = None
    lock = threading.Lock()
    stats = {"requests": 0, "blocks": 0, "errors": 0}

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self._send(200, {
                "status": "ok",
                "version": __version__,
                "endpoint": self.args.endpoint,
                "model": self.args.model,
                "limit_concurrency": self.args.limit_concurrency,
                "max_concurrency": MAX_CONCURRENCY,
                "stats": self.stats,
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/guard":
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        try:
            if content_type == "application/json":
                request = json.loads(raw or b"{}")
            else:
                request = {"text": raw.decode("utf-8", "replace")}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send(400, {"error": f"ungueltiger Body: {exc}"})
            return
        if not isinstance(request, dict):
            self._send(400, {"error": "Body muss ein JSON-Objekt sein"})
            return

        try:
            result = guard(
                request.get("text", ""),
                mode=request.get("mode", self.args.mode),
                fail_open=bool(request.get("fail_open", self.args.fail_open)),
                endpoint=request.get("endpoint", self.args.endpoint),
                model=request.get("model", self.args.model),
                timeout=float(request.get("timeout", self.args.timeout)),
                workers=int(request.get("workers", self.args.workers)),
            )
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return

        with self.lock:
            self.stats["requests"] += 1
            if result["decision"] == "block":
                self.stats["blocks"] += 1
        self._send(200, result)

    def log_message(self, fmt, *args):
        if self.args.verbose:
            sys.stderr.write("[api] " + fmt % args + "\n")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # Standard waere 5; bei vielen gleichzeitigen Anfragen kommen sonst
    # ConnectionResetError statt sauberer Antworten (gemessen bei 30).
    request_queue_size = 256
    # Obergrenze gleichzeitig bearbeiteter Anfragen; None heisst unbegrenzt.
    limit_concurrency = None


def install_limit(server):
    """Begrenzt die gleichzeitig bearbeiteten Anfragen auf
    Server.limit_concurrency.

    ThreadingHTTPServer ruft process_request je neuer Anfrage auf. Hier wird
    auf einen freien Platz gewartet; ohne Grenze laeuft die Anfrage sofort.
    """
    if not Server.limit_concurrency:
        return
    slots = threading.BoundedSemaphore(Server.limit_concurrency)
    original = server.process_request

    def limited(request, client_address):
        with slots:
            return original(request, client_address)

    server.process_request = limited


def build_parser():
    parser = argparse.ArgumentParser(
        prog="laya-guardrail",
        description="HTTP-API der Laya-Guardrail (Regeln R1 bis R4)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help="Laya-Endpunkt (ueber llama-swap)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Zeitgrenze je Anfrage an Laya, in Sekunden")
    parser.add_argument("--workers", type=int, default=MAX_CONCURRENCY,
                        help=f"gleichzeitige Anfragen an Laya (Deckel: {MAX_CONCURRENCY})")
    parser.add_argument("--limit-concurrency", type=int,
                        default=DEFAULT_LIMIT_CONCURRENCY,
                        help="gleichzeitig bearbeitete HTTP-Anfragen; "
                             "0 bedeutet unbegrenzt")
    parser.add_argument("--fail-open", action="store_true",
                        help="bei Fehler PASS statt BLOCK (Standard: BLOCK)")
    parser.add_argument("--verbose", action="store_true",
                        help="jede Anfrage ins Protokoll schreiben")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    Handler.args = args
    Server.limit_concurrency = args.limit_concurrency or None
    server = Server((args.host, args.port), Handler)
    install_limit(server)
    sys.stderr.write(
        f"[api] lauscht auf http://{args.host}:{args.port}/guard  "
        f"(Laya: {args.endpoint}, Modell {args.model}, "
        f"limit_concurrency={args.limit_concurrency or 'unbegrenzt'}, "
        f"workers={args.workers}, fail_open={args.fail_open})\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[api] beendet\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
