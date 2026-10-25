"""Request intent, rules-only adapter (ADR 0008 fallback; the cached LLM adapter comes in T11).

DELETION needs a deletion cue and no negation/scope cue. The default is NOT_DELETION, because a
request that never asks to delete, erase, remove or close does not authorize deletion
(AGENTS.md §6.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DELETION_CUES = [
    r"\bdelet\w*",
    r"\beras\w*",
    r"\bremov\w*",
    r"\bclos(?:e|ed|ing|ure)\b",
    r"\bpurg\w*",
    r"\bwip\w*",
    r"\bforget me\b",
    r"\bis gone\b",
    r"\bno longer exists?\b",
    r"\bcannot identify me\b",
    r"\bexclus\w*",
    r"\bexclu[ií]\w*",
    r"\belimin\w*",
    r"\bborr\w*",
    r"\bsuppression\b",
    r"\bsupprim\w*",
    r"\beffac\w*",
    r"\blösch\w*",
    r"\bloesch\w*",
    "削除",
    "삭제",
    "删除",
]
NEGATION_CUES = [
    r"\bnot (?:asking|requesting) (?:for )?(?:a )?(?:deletion|erasure|removal)",
    r"\bnot a request to (?:erase|delete|remove|close)",
    r"\b(?:do not|don't|dont|please don't|without) (?:delet\w*|eras\w*|remov\w*|clos\w*)",
    r"\blists? only\b",
    r"\bmarketing (?:lists|emails)\b",
    r"\bpromotional emails\b",
    r"\bleave (?:the|my) (?:account|profile)\b",
    r"\bkeep (?:the|my) account\b",
    r"\bcontinue using\b",
    r"\bstill (?:need|use|want) (?:the|this|my|it)\b",
]
_del = [re.compile(p, re.I) for p in DELETION_CUES]
_neg = [re.compile(p, re.I) for p in NEGATION_CUES]


@dataclass
class Intent:
    label: str  # DELETION | NOT_DELETION
    reason: str
    source: str = "rules"


def classify_rules(text: str | None) -> Intent:
    t = text or ""
    neg = next((p.pattern for p in _neg if p.search(t)), None)
    if neg:
        return Intent("NOT_DELETION", f"negation/scope cue {neg!r}")
    cue = next((p.pattern for p in _del if p.search(t)), None)
    if cue:
        return Intent("DELETION", f"deletion cue {cue!r}")
    return Intent("NOT_DELETION", "no deletion cue")
