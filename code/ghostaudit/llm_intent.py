"""Intent: rules pre-screen, cached model for the remainder (ADR 0008).

  IntentClassifier(client, cache, tracker).classify(text) -> Intent(label, reason, source)
  .review(text)  -> model verdict for any text (evaluation: rules vs model confusion); disagreements
  recorded

Decision:
  * clear rules case: a deletion cue and no negation/scope cue (DELETION), or a negation/scope cue
    and no
    deletion cue (NOT_DELETION) -> rules decide;
  * remainder (both cues, or neither) -> the model's atomic yes/no answers decide:
      DELETION iff (asks_to_delete or asks_to_verify_or_finish_deletion) and not excludes_deletion;
  * no model verdict available (no key and no cache entry) -> the rules label, marked as such.
Model verdicts come from the committed cache first (code/ghostaudit/llm_cache.py, keyed by
sha256(model + prompt + text)); a live call happens only on a cache miss with OPENAI_API_KEY set.
The key is read by the SDK from the environment and never touched here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from collections.abc import Iterable, Mapping
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

from ghostaudit.intent import Intent, _del, _neg, classify_rules

if TYPE_CHECKING:
    from ghostaudit.usage import Tracker

# a cache entry: {'answers': {...}, 'label': 'DELETION' | 'NOT_DELETION', 'model': id}
Entry = dict[str, Any]
MODEL = "gpt-5.4-mini-2026-03-17"
SEED = 20261025
REQUEST_TIMEOUT_SECONDS = 30  # one API request; a slower answer counts as a failed attempt
RETRY_BACKOFF_SECONDS = 0.5  # sleep before retry n is n times this
PREFETCH_WORKERS = 8  # parallel live calls when the cache is filled ahead of a run
MAX_RETRIES = 2  # per text, after the first attempt; then the rules decide (never a crash)
_warned: set[str] = set()  # warning keys already printed this process
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "intent_classifier.md"
CACHE_PATH = Path(__file__).resolve().parent / "llm_cache.py"
SCHEMA = {
    "name": "intent_answers",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "asks_to_delete",
            "asks_to_verify_or_finish_deletion",
            "excludes_deletion",
            "rationale",
        ],
        "properties": {
            "asks_to_delete": {"type": "boolean"},
            "asks_to_verify_or_finish_deletion": {"type": "boolean"},
            "excludes_deletion": {"type": "boolean"},
            "rationale": {"type": "string"},
        },
    },
}


def prompt_text() -> str:
    """The committed classifier prompt (code/prompts/intent_classifier.md)."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def cache_key(text: str, prompt: str | None = None, model: str = MODEL) -> str:
    """Cache key of one model verdict: sha256 of model id, prompt and request text.

    Any change to the model, the prompt or the text is a different key, so a stale verdict is
    never reused."""
    return hashlib.sha256(
        f"{model}\n{prompt if prompt is not None else prompt_text()}\n{text}".encode()
    ).hexdigest()


def build_messages(text: str | None, prompt: str | None = None) -> list[dict[str, str]]:
    """Chat messages for one request: the prompt, then the text inside delimiters.

    Delimiter look-alikes inside the text are broken up, so a request cannot close its own
    quotation and pose as instructions."""
    safe = (text or "").replace("MESSAGE>>>", "MESSAGE> > >").replace("<<<MESSAGE", "< < <MESSAGE")
    return [
        {"role": "system", "content": prompt if prompt is not None else prompt_text()},
        {"role": "user", "content": f"<<<MESSAGE\n{safe}\nMESSAGE>>>"},
    ]


def label(answers: Mapping[str, Any]) -> str:
    """DELETION iff the answers ask to delete (or to verify or finish a deletion) and do
    not exclude deletion; otherwise NOT_DELETION."""
    asks = answers["asks_to_delete"] or answers["asks_to_verify_or_finish_deletion"]
    return "DELETION" if asks and not answers["excludes_deletion"] else "NOT_DELETION"


def rules_clarity(text: str) -> str:
    """'clear' when the rules' cues point one way only; 'remainder' when both or neither fire."""
    de, neg = any(p.search(text) for p in _del), any(p.search(text) for p in _neg)
    return "clear" if de != neg else "remainder"


def _cache_module(path: str | Path) -> ModuleType:
    """Execute the generated cache file as a module (it holds only literals)."""
    spec = cast(ModuleSpec, importlib.util.spec_from_file_location("ghostaudit_llm_cache", path))
    mod = importlib.util.module_from_spec(spec)
    cast(Loader, spec.loader).exec_module(mod)
    return mod


def read_cache(path: str | Path = CACHE_PATH) -> dict[str, Entry]:
    """Model verdicts committed in the cache file, by cache_key; {} if there is none."""
    if not Path(path).exists():
        return {}
    return dict(_cache_module(path).CACHE)


def read_origin(path: str | Path = CACHE_PATH) -> list[dict[str, Any]]:
    """The runs that added entries to the cache (live calls and tokens each); [] if unknown."""
    if not Path(path).exists():
        return []
    return list(getattr(_cache_module(path), "ORIGIN", []))


def write_cache(
    path: str | Path, cache: Mapping[str, Entry], origin: list[dict[str, Any]] | None = None
) -> None:
    """origin=None keeps the ORIGIN already in the file."""
    origin = read_origin(path) if origin is None else origin
    lines = [
        '"""GENERATED by ghostaudit.llm_intent: cached model verdicts for request intent (ADR '
        "0008).",
        "Keys are sha256(model + prompt + request text); values hold the model's answers only, "
        "never the text.",
        "ORIGIN lists the runs that added entries (calls and tokens only).",
        'Do not edit by hand; delete an entry to force a new call."""',
        "",
        f"ORIGIN = {origin!r}",
        "",
        "CACHE = {",
    ]
    for k in sorted(cache):
        lines.append(f"    {k!r}: {cache[k]!r},")
    lines += ["}", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def _warn_once(key: str, message: str, tracker: Tracker | None = None) -> None:
    if key in _warned:
        return
    _warned.add(key)
    print(f"WARNING: {message}", file=sys.stderr)
    if tracker is not None:
        tracker.note(message)


def default_client(tracker: Tracker | None = None) -> Any:
    """An OpenAI client when OPENAI_API_KEY is set and the optional `openai` package imports.

    Otherwise None. A key without the package degrades to rules + cache with one warning, never a
    crash. The SDK reads the key from the environment; this function never touches it."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
    except ImportError:
        _warn_once(
            "sdk",
            "OPENAI_API_KEY is set but the optional `openai` package is not installed; "
            "intent uses rules + the committed cache",
            tracker,
        )
        return None
    return OpenAI(
        max_retries=0, timeout=REQUEST_TIMEOUT_SECONDS
    )  # retries are bounded here (MAX_RETRIES), not inside the SDK


def _valid(answers: object) -> bool:
    keys = ("asks_to_delete", "asks_to_verify_or_finish_deletion", "excludes_deletion")
    return (
        isinstance(answers, dict)
        and all(isinstance(answers.get(k), bool) for k in keys)
        and isinstance(answers.get("rationale"), str)
    )


class IntentClassifier:
    """Intent for request texts: rules for clear texts, the model for the remainder.

    Model verdicts come from the cache first; a live call happens only on a cache miss with a
    client. Failed calls are retried MAX_RETRIES times, then the rules decide (never a crash).
    New verdicts are kept in memory until save()."""

    def __init__(
        self,
        client: Any = None,
        cache: dict[str, Entry] | None = None,
        tracker: Tracker | None = None,
        prompt: str | None = None,
        backoff: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        self.client, self.tracker, self.backoff = client, tracker, backoff
        self.cache = read_cache() if cache is None else cache
        self.prompt = prompt if prompt is not None else prompt_text()
        self.disagreements: list[dict[str, str]] = []
        self.new_entries = 0
        self.failed: set[str] = (
            set()
        )  # keys whose live call failed this run: not retried again, never cached
        self._decided: dict[str, str] = {}  # text -> source, for the end-of-run summary

    @property
    def counts(self) -> dict[str, int]:
        """How many unique texts each source decided (rules, cache, live model, fallbacks)."""
        from collections import Counter

        c = Counter(self._decided.values())
        return {
            "rules": c["rules"],
            "cache": c["model (cache)"],
            "model": c["model"],
            "rules_fallback": c["rules (no model verdict)"],
            "degraded": c["rules (model error)"],
        }

    def summary(self) -> str:
        """One line with the per-source decision counts, for the run log."""
        c = self.counts
        return (
            f"intent decisions ({len(self._decided)} unique texts): rules (clear) {c['rules']}, "
            f"cache {c['cache']}, "
            f"live model {c['model']}, rules fallback {c['rules_fallback']}, degraded by error "
            f"{c['degraded']}"
        )

    def _live(self, text: str, key: str) -> dict[str, Any] | None:
        """One text through the API with bounded retries; None (and a recorded failure) if every
        attempt fails."""
        errors = []
        t0 = time.perf_counter()
        for attempt in range(1 + MAX_RETRIES):
            try:
                resp = self.client.chat.completions.create(
                    model=MODEL,
                    messages=build_messages(text, self.prompt),
                    seed=SEED,
                    reasoning_effort="none",
                    response_format={"type": "json_schema", "json_schema": SCHEMA},
                    store=False,
                )
                answers = json.loads(resp.choices[0].message.content)
                if not _valid(answers):
                    raise ValueError("answer violates the schema")
                u = resp.usage
                if self.tracker:
                    self.tracker.record(
                        "openai",
                        MODEL,
                        u.prompt_tokens,
                        u.completion_tokens,
                        (time.perf_counter() - t0) * 1000,
                        cache_hit=False,
                    )
                return answers
            except Exception as e:  # auth, connection, timeout, rate limit, bad JSON, schema
                errors.append(f"{type(e).__name__}: {str(e)[:120]}")
                if attempt < MAX_RETRIES and self.backoff:
                    time.sleep(self.backoff * (attempt + 1))
        self.failed.add(key)
        if self.tracker:
            self.tracker.record_failure(
                "openai", MODEL, len(errors), (time.perf_counter() - t0) * 1000, errors[-1]
            )
        _warn_once(
            "api",
            f"intent model call failed ({errors[-1]}); falling back to rules for affected texts",
            self.tracker,
        )
        return None

    def _verdict(self, text: str) -> tuple[Entry | None, bool]:
        key = cache_key(text, self.prompt)
        hit = self.cache.get(key)
        if hit is not None:
            if self.tracker:
                self.tracker.record("openai", hit["model"], 0, 0, 0.0, cache_hit=True)
            return hit, True
        if self.client is None or key in self.failed:
            return None, False
        answers = self._live(text, key)
        if answers is None:
            return None, False
        entry = {"answers": answers, "label": label(answers), "model": MODEL}
        self.cache[key] = entry
        self.new_entries += 1
        return entry, False

    def prefetch(self, texts: Iterable[str], workers: int = PREFETCH_WORKERS) -> int:
        """Fill the cache for many texts with parallel live calls (cache misses only); results
        are order-free."""
        from concurrent.futures import ThreadPoolExecutor

        todo = sorted({t for t in texts if cache_key(t, self.prompt) not in self.cache})
        if self.client is None or not todo:
            return 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(self._verdict, todo))
        return len(todo)

    def review(self, text: str) -> Entry | None:
        """Model verdict for any text, compared with the rules (records disagreements)."""
        v, _ = self._verdict(text)
        r = classify_rules(text)
        if v and v["label"] != r.label:
            self.disagreements.append(
                {
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
                    "rules": r.label,
                    "model": v["label"],
                    "rules_reason": r.reason,
                    "model_rationale": v["answers"]["rationale"],
                    "clarity": rules_clarity(text),
                }
            )
        return v

    def classify(self, text: str) -> Intent:
        """The Intent for `text` (see the module docstring for who decides).

        The deciding source is recorded once per unique text for counts and summary."""
        out = self._classify(text)
        self._decided.setdefault(text, out.source)
        return out

    def _classify(self, text: str) -> Intent:
        r = classify_rules(text)
        if rules_clarity(text) == "clear":
            return r
        v, cached = self._verdict(text)
        if v is None:
            if cache_key(text, self.prompt) in self.failed:
                return Intent(r.label, r.reason + "; model call failed", "rules (model error)")
            return Intent(
                r.label,
                r.reason + "; no model verdict (no key, cache miss)",
                "rules (no model verdict)",
            )
        return Intent(v["label"], v["answers"]["rationale"], "model (cache)" if cached else "model")

    def save(self, path: str | Path = CACHE_PATH) -> None:
        """Write the cache file if this run added verdicts, appending one ORIGIN record
        (time, live calls, tokens, entries added). Nothing is written when no entry is new."""
        if self.new_entries:
            m = (
                self.tracker.totals()["per_model"].get(MODEL, {})
                if self.tracker is not None
                else {}
            )
            run = {
                "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "live_calls": m.get("calls", 0),
                "input_tokens": m.get("input_tokens", 0),
                "output_tokens": m.get("output_tokens", 0),
                "entries_added": self.new_entries,
            }
            write_cache(path, self.cache, read_origin(path) + [run])
