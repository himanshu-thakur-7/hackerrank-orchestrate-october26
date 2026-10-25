"""Model usage tracker: one record per model lookup (live call or cache hit), with totals for
usage_report.md.

Prices are USD per 1M tokens (input, output), from the provider's model page
(https://developers.openai.com/api/docs/models/gpt-5.4-mini, checked 2026-10-25).

Decisions: ADR 0008 (model calls are cached; a cache hit is counted, never billed).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PRICE_PER_MTOK = {"gpt-5.4-mini-2026-03-17": (0.75, 4.50)}


@dataclass(frozen=True)
class Call:
    """One model lookup: a live call (tokens, latency) or a cache hit (zero tokens)."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cache_hit: bool


def _cost(call: Call) -> float:
    """Estimated USD for one live call; a model without a listed price costs 0."""
    price_in, price_out = PRICE_PER_MTOK.get(call.model, (0, 0))
    return (call.input_tokens * price_in + call.output_tokens * price_out) / 1e6


def _per_model(live: list[Call]) -> dict[str, dict[str, Any]]:
    per_model: dict[str, dict[str, Any]] = {}
    for c in live:
        m = per_model.setdefault(
            c.model, {"provider": c.provider, "calls": 0, "input_tokens": 0, "output_tokens": 0}
        )
        m["calls"] += 1
        m["input_tokens"] += c.input_tokens
        m["output_tokens"] += c.output_tokens
    return per_model


def _cache_hits_per_model(calls: list[Call]) -> dict[str, int]:
    hits = [c.model for c in calls if c.cache_hit]
    return {m: hits.count(m) for m in sorted(set(hits))}


class Tracker:
    """Collects every model lookup of one run, plus failures and degradation notes.

    totals() and summary() feed the run log and usage_report.md. Only counts, tokens, latency
    and short error excerpts are kept: never a key or a request text."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        # texts whose live call failed after every retry (decided by rules instead)
        self.failures: list[dict[str, Any]] = []
        self.notes: list[str] = []  # run-level degradations (e.g. a key without the SDK)

    def note(self, message: str) -> None:
        """Record a run-level degradation once (repeats are ignored)."""
        if message not in self.notes:
            self.notes.append(message)

    def record_failure(
        self, provider: str, model: str, attempts: int, latency_ms: float, error: str
    ) -> None:
        """Record a text whose live call failed after every attempt."""
        self.failures.append(
            {
                "provider": provider,
                "model": model,
                "attempts": attempts,
                "latency_ms": round(latency_ms, 1),
                "error": error,
            }
        )

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cache_hit: bool,
    ) -> None:
        """Record one model lookup: a live call with its tokens, or a cache hit."""
        self.calls.append(
            Call(
                provider,
                model,
                int(input_tokens),
                int(output_tokens),
                round(float(latency_ms), 1),
                bool(cache_hit),
            )
        )

    def totals(self) -> dict[str, Any]:
        """Run totals: live calls with their tokens and cost, cache hits, degradations and notes."""
        live = [c for c in self.calls if not c.cache_hit]
        return {
            "calls": len(live),
            "cache_hits": len(self.calls) - len(live),
            "degraded": len(self.failures),
            "failed_attempts": sum(f["attempts"] for f in self.failures),
            "notes": list(self.notes),
            "input_tokens": sum(c.input_tokens for c in live),
            "output_tokens": sum(c.output_tokens for c in live),
            "latency_ms_total": round(sum(c.latency_ms for c in live), 1),
            "cost_usd": sum(_cost(c) for c in live),
            "per_model": _per_model(live),
            "cache_hits_per_model": _cache_hits_per_model(self.calls),
        }

    def summary(self) -> str:
        """One line with calls, cache hits, tokens, estimated cost and degradations."""
        t = self.totals()
        avg = (t["input_tokens"] + t["output_tokens"]) / t["calls"] if t["calls"] else 0
        return (
            f"model usage: {t['calls']} live call(s), {t['cache_hits']} cache hit(s); tokens in "
            f"{t['input_tokens']} / out "
            f"{t['output_tokens']} (avg {avg:.0f} per call); est. cost ${t['cost_usd']:.4f}; "
            f"degraded texts {t['degraded']}"
            + (f"; notes: {' | '.join(t['notes'])}" if t["notes"] else "")
        )

    def rows(self) -> list[dict[str, Any]]:
        """Every recorded call as a plain dict, in call order."""
        return [asdict(c) for c in self.calls]


def write_run_log(directory: str | Path, tracker: Tracker) -> None:
    """Per-call records of one run as Markdown under runs/ (git-ignored); totals feed
    usage_report.md."""
    import time
    from pathlib import Path

    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    t = tracker.totals()
    lines = (
        [
            f"# Model usage, run {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            f"- live calls {t['calls']}, cache hits {t['cache_hits']}, input tokens "
            f"{t['input_tokens']}, "
            f"output tokens {t['output_tokens']}, est. cost ${t['cost_usd']:.4f}, degraded texts "
            f"{t['degraded']} "
            f"({t['failed_attempts']} failed attempts)",
            "",
        ]
        + [f"- note: {n}" for n in t["notes"]]
        + [f"- failure: {f['error']} after {f['attempts']} attempts" for f in tracker.failures]
        + [
            "",
            "| provider | model | input | output | latency ms | cache hit |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    lines += [
        f"| {c.provider} | {c.model} | {c.input_tokens} | {c.output_tokens} | {c.latency_ms} | "
        f"{c.cache_hit} |"
        for c in tracker.calls
    ]
    (d / f"usage_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
