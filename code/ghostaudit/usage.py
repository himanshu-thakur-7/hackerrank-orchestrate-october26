"""Model usage tracker: one record per model lookup (live call or cache hit), with totals for usage_report.md.

Prices are USD per 1M tokens (input, output), from the provider's model page
(https://developers.openai.com/api/docs/models/gpt-5.4-mini, checked 2026-10-25).
"""
from dataclasses import asdict, dataclass

PRICE_PER_MTOK = {"gpt-5.4-mini-2026-03-17": (0.75, 4.50)}


@dataclass(frozen=True)
class Call:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cache_hit: bool


class Tracker:
    def __init__(self):
        self.calls = []
        self.failures = []      # texts whose live call failed after every retry (decided by rules instead)
        self.notes = []         # run-level degradations (e.g. a key without the SDK)

    def note(self, message):
        if message not in self.notes:
            self.notes.append(message)

    def record_failure(self, provider, model, attempts, latency_ms, error):
        self.failures.append({"provider": provider, "model": model, "attempts": attempts, "latency_ms": round(latency_ms, 1), "error": error})

    def record(self, provider, model, input_tokens, output_tokens, latency_ms, cache_hit):
        self.calls.append(Call(provider, model, int(input_tokens), int(output_tokens), round(float(latency_ms), 1), bool(cache_hit)))

    def totals(self):
        live = [c for c in self.calls if not c.cache_hit]
        cost = sum((c.input_tokens * PRICE_PER_MTOK.get(c.model, (0, 0))[0] + c.output_tokens * PRICE_PER_MTOK.get(c.model, (0, 0))[1]) / 1e6
                   for c in live)
        per_model = {}
        for c in live:
            m = per_model.setdefault(c.model, {"provider": c.provider, "calls": 0, "input_tokens": 0, "output_tokens": 0})
            m["calls"] += 1; m["input_tokens"] += c.input_tokens; m["output_tokens"] += c.output_tokens
        return {"calls": len(live), "cache_hits": len(self.calls) - len(live), "degraded": len(self.failures),
                "failed_attempts": sum(f["attempts"] for f in self.failures), "notes": list(self.notes),
                "input_tokens": sum(c.input_tokens for c in live), "output_tokens": sum(c.output_tokens for c in live),
                "latency_ms_total": round(sum(c.latency_ms for c in live), 1), "cost_usd": cost, "per_model": per_model}

    def summary(self):
        t = self.totals()
        avg = (t["input_tokens"] + t["output_tokens"]) / t["calls"] if t["calls"] else 0
        return (f"model usage: {t['calls']} live call(s), {t['cache_hits']} cache hit(s); tokens in {t['input_tokens']} / out "
                f"{t['output_tokens']} (avg {avg:.0f} per call); est. cost ${t['cost_usd']:.4f}; degraded texts {t['degraded']}"
                + (f"; notes: {' | '.join(t['notes'])}" if t["notes"] else ""))

    def rows(self):
        return [asdict(c) for c in self.calls]


def write_run_log(directory, tracker):
    """Per-call records of one run as Markdown under runs/ (git-ignored); totals feed usage_report.md."""
    import time
    from pathlib import Path
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    t = tracker.totals()
    lines = [f"# Model usage, run {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", "",
             f"- live calls {t['calls']}, cache hits {t['cache_hits']}, input tokens {t['input_tokens']}, "
             f"output tokens {t['output_tokens']}, est. cost ${t['cost_usd']:.4f}, degraded texts {t['degraded']} "
             f"({t['failed_attempts']} failed attempts)", ""] + [f"- note: {n}" for n in t["notes"]] + [
             f"- failure: {f['error']} after {f['attempts']} attempts" for f in tracker.failures] + ["",
             "| provider | model | input | output | latency ms | cache hit |", "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {c.provider} | {c.model} | {c.input_tokens} | {c.output_tokens} | {c.latency_ms} | {c.cache_hit} |" for c in tracker.calls]
    (d / f"usage_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
