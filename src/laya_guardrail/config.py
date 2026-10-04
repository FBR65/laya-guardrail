"""Feste Werte des Pakets: Endpunkte, Schwellen, Grenzen.

Alle Werte sind hier gebuendelt, damit Regeln und Grenzen an einer Stelle
nachvollziehbar sind. Gemessene Werte tragen die Messung als Kommentar.
"""

# --- Anbindung an Laya ------------------------------------------------------

# llama-swap hoert auf 8080 und proxyt /v1/systemone an den laya-Prozess.
DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1/systemone"
DEFAULT_MODEL = "laya-multilingual"

# Gemessen an llama-swap: mehr als 10 gleichzeitige Anfragen ergeben HTTP 429
# mit dem Code "concurrency_limit". Darum geht nie mehr als das gleichzeitig
# an Laya; die API selbst nimmt beliebig viele Saetze an.
MAX_CONCURRENCY = 10

# --- Schwellen der Regeln ---------------------------------------------------
#
#   R1  jailbreak > 0.5 oder prompt_injection > 0.9    -> BLOCK
#   R2  sensitive_data > 0.5                          -> BLOCK
#   R3  harm_severity >= 2.3                          -> BLOCK
#   R4  Sprache ist nicht Deutsch                     -> BLOCK
#
# Herkunft der Werte:
#   prompt_injection 0.9: bei 0.5 schlug die Regel auf sauberen Geschaeftssaetzen
#     an (gemessener Fehlalarm 0.749); echte Injektionen liegen bei 0.9 bis 1.0.
#   harm 2.3: die Brandsatz-Anleitung liegt bei 2.44 bis 2.45, harmlose Bloecke
#     bei 2.01 bis 2.30. Der Abstand ist duenn.

THRESH_NOUL = 0.5
THRESH_INJECTION = 0.9
THRESH_HARM = 2.3

# R3 laeuft nicht pro Satz, sondern auf Bloecken dieser Groesse. Satzweise hebt
# harm_severity harmlose Saetze ueber die Schwelle (gemessen bis 2.55).
R3_GROUP_SIZE = 10

# --- Zielsprache ------------------------------------------------------------

# Ist die erkannte Sprache eines Satzes nicht diese, blockt R4.
LANG_TARGET = "de"

# --- Modus und Satztrennung -------------------------------------------------

# Satztrennung ist der Standard. "whole" (der Gesamttext als ein Prompt)
# liefert auf mehrsaetzigen Texten keinen verwertbaren Wert: Laya wertet den
# Gesamttext fast immer als jailbreak, injection und sensible Daten und blockt
# damit jeden laengeren Text. "whole" muss ausdruecklich angefordert werden.
DEFAULT_MODE = "sentences"

VALID_MODES = ("sentences", "whole", "both")

# Stuecke unter dieser Laenge werden nicht als eigener Satz abgetrennt. Sonst
# entstehen Bruchstuecke wie "z." oder "Danke." als Einzelsatz.
MIN_SENTENCE = 20

# Wiederholungen bei HTTP 429 und 503 (llama-swap-Deckel, Ueberlast).
RETRY_ATTEMPTS = 5
RETRY_BASE_DELAY = 0.25
