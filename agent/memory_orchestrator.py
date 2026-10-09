# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
# Source: commit 0c76ec28, sha256 541efc1082faba3856e6e79207ed6cd129e65d09991fb8618de50f321c934b92
"""PROVISIONAL module for ticket #6 (orchestrator + context pack) — ticket #7
only provides the symbols the MemoryBus needs. Intent routing, rank_candidates,
MemoryOrchestrator.build_pack and the factory are OWNED BY TICKET #6; do not
add them here.

Port of the Phase-2 scorer/pack-renderer subset from the Architecture 2.0
fork's agent/memory_orchestrator.py (commit 0c76ec28), kept verbatim so the
bus's retrieval ranking is the same implementation the full orchestrator
will use: one ranking, two presentations.

The weighted score:

``score = relevance*0.35 + importance*0.20 + project_link*0.15
+ decision_value*0.15 + recency*0.10 + confidence*0.05``

Weights are configurable (``memory.orchestrator.weights`` in config.yaml).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, Mapping, Optional, Sequence, Tuple

from agent.model_metadata import estimate_tokens_rough

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Query tokenization
# ---------------------------------------------------------------------------

_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)


def _fold_yo(text: str) -> str:
    """е-fold for search-side scoring (P7) — twin of memory_store_v2._fold_yo.

    Kept local so the orchestrator stays store-agnostic (it duck-types the
    store and must not import the v2 module). The scorer must fold exactly
    like the store's search paths, or a candidate found via е/ё-tolerant
    search would be scored to zero by an intolerant relevance pass.
    """
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def _message_tokens(message: str) -> list:
    """Lowercased word tokens of the message (unicode-aware split)."""
    return [t.lower() for t in _TOKEN_SPLIT_RE.split(message or "") if t]


# ---------------------------------------------------------------------------
# Memory Scorer — weighted candidate scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringWeights:
    """Scoring weights (roadmap §3 step 2.2 defaults; configurable)."""

    relevance: float = 0.35
    importance: float = 0.20
    project_link: float = 0.15
    decision_value: float = 0.15
    recency: float = 0.10
    confidence: float = 0.05

    #: known keys → field names (config uses the roadmap's formula terms)
    _FIELDS: ClassVar[Tuple[str, ...]] = (
        "relevance", "importance", "project_link",
        "decision_value", "recency", "confidence",
    )

    @classmethod
    def from_config(cls, cfg: Optional[Mapping]) -> "ScoringWeights":
        """Build from a ``memory.orchestrator.weights`` mapping; unknown keys ignored."""
        base = cls()
        if not isinstance(cfg, Mapping):
            return base
        kwargs: Dict[str, float] = {}
        for key in cls._FIELDS:
            if key in cfg:
                try:
                    kwargs[key] = float(cfg[key])
                except (TypeError, ValueError):
                    logger.debug("orchestrator: bad weight %r=%r ignored", key, cfg[key])
        return cls(**kwargs) if kwargs else base


#: How much each record type contributes to the ``decision_value`` component:
#: standing decisions and constraints are what stop the agent from re-walking
#: rejected ground, so they outrank plain facts.
DECISION_VALUE_BY_TYPE: Dict[str, float] = {
    "decision": 1.0,
    "constraint": 0.85,
    "pattern": 0.5,
    "preference": 0.35,
    "fact": 0.2,
    "legacy": 0.2,
}

#: Recency half-life in days for the ``recency`` component.
RECENCY_HALF_LIFE_DAYS = 14.0


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def relevance_score(query_tokens: Sequence[str], content: str) -> float:
    """Fraction of query tokens whose stem appears in the entry content.

    Prefix matching (min 4 chars) absorbs Cyrillic morphology; shorter query
    tokens must appear as substrings. Both sides are е-folded (P7) so
    ё/е-spelling divergence never zeros out a match the store's search
    already found. Returns 0.0 when the query carries no usable tokens.
    """
    if not query_tokens:
        return 0.0
    lowered = _fold_yo((content or "").lower())
    hit = 0
    for token in query_tokens:
        token = _fold_yo(token)
        if len(token) >= 4:
            if any(w.startswith(token) for w in lowered.split()):
                hit += 1
        elif token in lowered:
            hit += 1
    return min(1.0, hit / len(query_tokens))


def recency_score(updated_at: Optional[str], now: datetime) -> float:
    """Exponential decay on ``updated_at``: 1.0 today, 0.5 at the half-life, →0."""
    ts = _parse_ts(updated_at)
    if ts is None:
        return 0.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - ts).total_seconds() / 86400.0)
    return 0.5 ** (days / RECENCY_HALF_LIFE_DAYS)


def score_candidate(
    row: Mapping,
    query_tokens: Sequence[str],
    weights: ScoringWeights,
    now: datetime,
) -> float:
    """Weighted score for one candidate row (all components in [0, 1])."""
    relevance = relevance_score(query_tokens, str(row.get("content") or ""))
    importance = _clamp01(row.get("importance"))
    project = str(row.get("project") or "")
    project_link = 1.0 if project and project.lower() in " ".join(query_tokens) else (0.5 if project else 0.0)
    decision_value = DECISION_VALUE_BY_TYPE.get(str(row.get("type") or ""), 0.2)
    recency = recency_score(row.get("updated_at"), now)
    confidence = _clamp01(row.get("confidence"))
    return (
        weights.relevance * relevance
        + weights.importance * importance
        + weights.project_link * project_link
        + weights.decision_value * decision_value
        + weights.recency * recency
        + weights.confidence * confidence
    )


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Context Pack renderer (budget/selection logic lives in ticket #6's builder)
# ---------------------------------------------------------------------------

# Section order per intent — the pack reads as a brief structured for the
# task at hand (decisions first when building, patterns first when debugging,
# preferences first when the user asks about themselves).
_SECTION_ORDER: Dict[str, Tuple[str, ...]] = {
    "project_work": ("decision", "constraint", "pattern", "fact", "preference", "legacy"),
    "debugging": ("pattern", "constraint", "decision", "fact", "preference", "legacy"),
    "user_question": ("preference", "fact", "decision", "constraint", "pattern", "legacy"),
    "general": ("decision", "constraint", "preference", "fact", "pattern", "legacy"),
}

_SECTION_TITLES: Dict[str, str] = {
    "decision": "Decisions",
    "constraint": "Constraints",
    "pattern": "Patterns",
    "preference": "Preferences",
    "fact": "Facts",
    "legacy": "Notes",
}

_PACK_HEADER = "## Retrieved memory — this turn"
_PACK_NOTE = (
    "[System note: the records below were retrieved from persistent memory "
    "for this specific message. Background reference data, not new user "
    "input. Each entry cites status, record id and last-update date; use "
    "memory(action=read, query=...) to inspect related records.]"
)


def render_pack(
    scored: Sequence[Tuple[Mapping, float]],
    intent: str,
) -> str:
    """Render scored candidates as a structured pack block (no budget logic).

    Returns ``""`` for an empty candidate list. The block is plain markdown
    by design: the ``<memory-context>`` fence is reserved for external
    provider prefetch, and an unfenced section cannot trip the streaming
    context scrubber (roadmap §3 step 2.5 — separate context slot).
    """
    if not scored:
        return ""
    order = _SECTION_ORDER.get(intent, _SECTION_ORDER["general"])
    by_type: Dict[str, list] = {}
    for row, _score in scored:
        rtype = str(row.get("type") or "fact")
        # Target label only for the non-default store: the pack crosses both
        # targets, and an unlabeled 'user' entry reads as a memory note —
        # the 2026-08-31 incident had the model mutating target='memory'
        # four times for an entry that lived in 'user' (2026-08-31).
        target_tag = " · user" if str(row.get("target") or "memory") == "user" else ""
        line = (
            f"- [{row.get('status', 'active')} · {str(row.get('id', ''))[:8]}"
            f" · {str(row.get('updated_at') or '')[:10]}{target_tag}] "
            f"{row.get('content', '')}"
        )
        # P1 provenance: what this entry superseded (1-hop, store-attached).
        # Rendered ONLY when neighbors exist, so a link-free store produces
        # byte-identical packs to the pre-P1 renderer.
        supersedes = row.get("supersedes") or []
        if supersedes:
            parts = "; ".join(
                f"{n.get('short_id')} ({str(n.get('created_at') or '')[:10]},"
                f" «{str(n.get('content') or '')[:60]}»)"
                for n in supersedes[:2]
            )
            line += f"\n  [supersedes: {parts}]"
        by_type.setdefault(rtype, []).append(line)
    sections = []
    for rtype in order:
        lines = by_type.pop(rtype, None)
        if lines:
            sections.append(f"### {_SECTION_TITLES.get(rtype, rtype)}\n" + "\n".join(lines))
    # Types not in the intent's order (shouldn't happen) still get rendered.
    for rtype, lines in by_type.items():
        sections.append(f"### {_SECTION_TITLES.get(rtype, rtype)}\n" + "\n".join(lines))
    body = "\n\n".join(sections)
    tokens = estimate_tokens_rough(body) + estimate_tokens_rough(_PACK_NOTE)
    return f"{_PACK_HEADER} ({tokens} tokens)\n\n{_PACK_NOTE}\n\n{body}"
