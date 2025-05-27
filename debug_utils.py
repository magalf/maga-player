# debug_utils.py  ─────────────────────────────────────────────────────────
"""
Logging centralizzato per il Maga Player.
• Livelli      : TRACE < DEBUG < INFO < WARNING < ERROR < CRITICAL
• Formato base : 12:34:56.789  [THREAD]  [TAG]  messaggio  key=value ...
• Colorazione  : via colorlog (pip install colorlog) – fallback in B/W se non disponibile
• Integrazione : importa sempre `from debug_utils import dbg, trace, log_exception`
                 e rimpiazza i print manuali con dbg("TAG", "msg", k=v)
• Override print: tutte le print() legacy diventano DEBUG.
"""

import logging, sys, time, builtins

TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")

def _trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kws)
logging.Logger.trace = _trace                                     # type: ignore

def _make_handler():
    """
    Ritorna uno StreamHandler con colori (se colorlog è installato) e
    con timestamp HH:MM:SS, evitando l’uso di %f che su Windows
    provoca ValueError.
    """
    try:
        from colorlog import ColoredFormatter
        # es. "12:34:56  [MainThread] [DEBUG] messaggio"
        fmt = "%(log_color)s%(asctime)s [%(threadName)s] [%(levelname)s]%(reset)s " \
              "%(log_color)s%(message)s%(reset)s"
        cfmt = ColoredFormatter(fmt, datefmt="%H:%M:%S")
    except Exception:  # colorlog mancante
        cfmt = logging.Formatter("%(asctime)s [%(threadName)s] [%(levelname)s] %(message)s",
                                 "%H:%M:%S")
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(cfmt)
    return h

_root = logging.getLogger("Player")
_root.setLevel(TRACE_LEVEL)
_root.handlers.clear()
_root.propagate = False
_root.addHandler(_make_handler())

# --------------------------------------------------------------------- helpers
def dbg(tag: str, msg: str, **kv):
    extra = " ".join(f"{k}={v}" for k, v in kv.items())
    _root.debug(f"[{tag}] {msg} {extra}")

def trace(tag: str, msg: str, **kv):
    extra = " ".join(f"{k}={v}" for k, v in kv.items())
    _root.trace(f"[{tag}] {msg} {extra}")

def log_exception(tag: str, exc: Exception):
    _root.exception(f"[{tag}] {exc}")

NOTICE_LEVEL = 25
logging.addLevelName(NOTICE_LEVEL, "NOTICE")
def notice(self, message, *args, **kws):
    if self.isEnabledFor(NOTICE_LEVEL):
        self._log(NOTICE_LEVEL, message, args, **kws)
logging.Logger.notice = notice          # type: ignore

# --------------------------------------------------------------------- redirect print
def _print_redirect(*args, **kwargs):
    _root.debug(" ".join(str(a) for a in args))
# builtins.print = _print_redirect   # ← disattivato per evitare ricorsioni iniziali
# ────────────────────────────────────────────────────────────────────────
