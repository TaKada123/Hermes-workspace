# Ported from the Architecture 2.0 Hermes fork (MIT License)
# Copyright (c) 2025-2026 Dmitry Antipin (multi-agent orchestration fork)
# Source: commit 0c76ec28, sha256 541efc1082faba3856e6e79207ed6cd129e65d09991fb8618de50f321c934b92
"""Memory Orchestrator — Phase 2 of the memory roadmap.

Turns the built-in typed store (:class:`agent.memory_store_v2.MemoryStoreV2`)
from a static frozen snapshot into query-aware retrieval:

1. **Memory Router** — deterministic intent classification (project work /
   debugging / user question / general) selects which supplement layers to
   search and how the pack is laid out. No LLM on the retrieval path
   ("LLM advises, code decides"; anti-pattern: retrieval that depends on
   an LLM call — cost, latency, unstable scores).
2. **Memory Scorer** — weighted score per candidate:

   ``score = relevance*0.35 + importance*0.20 + project_link*0.15
   + decision_value*0.15 + recency*0.10 + confidence*0.05``

   Weights are configurable (``memory.orchestrator.weights`` in config.yaml).
3. **Token budget** — the pack is cut at ``memory.orchestrator.token_budget``
   (default 2500 tokens), most-scored entries first. Big memory must not
   become a big prompt.
4. **Context Pack Builder** — a structured markdown block (sections per
   record type, each line citing status + record id + date) instead of a
   raw concatenation. Record ids give the model provenance it can audit
   via ``memory(action=read)``.

Cache invariants (roadmap §1.4/§8):

- The frozen system-prompt snapshot is untouched; the pack is injected into
  the *API copy of the current turn's user message* only (same channel the
  external-provider prefetch uses), never into stored messages.
- Entries already present in the frozen snapshot are **excluded** from the
  pack — the pack is a supplement (what the char-budget evicted but this
  query needs), never a duplication. While memory fits the snapshot the
  pack is empty and nothing is injected: zero overhead, zero behavior
  change until memory outgrows the prompt budget.

Provenance note: the scorer/renderer subset (``ScoringWeights``,
``_message_tokens``, ``score_candidate``, ``render_pack``,
``relevance_score``, ``recency_score`` and the shared helpers) first landed
in this repository as a PROVISIONAL module provided by ticket #7 (the
MemoryBus imports those names at module level); their names and signatures
are kept verbatim. Ticket #6 completes the module with the deterministic
intent router, ``rank_candidates`` and the ``MemoryOrchestrator``/factory.

"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from agent.model_metadata import estimate_tokens_rough
# е-fold (P7) and the normalized matcher are owned by the store module — one
# definition, so the scorer folds EXACTLY like the store's search paths (a
# candidate found via е/ё-tolerant search must not score zero on an
# intolerant relevance pass). No import cycle: memory_store_v2 imports
# neither this module nor the bus.
from agent.memory_store_v2 import _fold_yo, match_normalized

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Memory Router — intent classification (deterministic)
# ---------------------------------------------------------------------------

INTENTS = ("project_work", "debugging", "user_question", "general")

# Token-prefix markers, matched case-insensitively against message tokens.
# Cyrillic markers rely on prefix-matching to absorb morphology
# ("ошибк" covers "ошибка/ошибки/ошибку"); latin markers of >=4 chars match
# the same way ("debug" covers "debugging"), shorter ones match whole words
# only (so "fix" never fires inside "prefix" — tokens are split, not
# substring-scanned). Order of the dicts = priority: debugging markers are
# the most specific, they win over project markers when both appear.
_INTENT_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "debugging",
        (
            "ошибк", "падает", "упал", "упала", "сломал", "почини",
            "трейсбек", "исключен", "баг", "дебаг",
            "traceback", "exception", "crash", "debug", "broken", "failing",
        ),
    ),
    (
        "project_work",
        (
            "реализ", "рефактор", "фича", "деплой", "проект", "архитектур",
            "скрипт", "миграц", "коммит", "код",
            "implement", "refactor", "feature", "deploy", "migrate",
            "schema", "build", "api",
        ),
    ),
    (
        "user_question",
        (
            "помнишь", "предпочитаю", "предпочтения", "привычк", "профиль",
            "remember", "prefer", "preferences",
        ),
    ),
)

_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)


def _message_tokens(message: str) -> List[str]:
    """Lowercased word tokens of the message (unicode-aware split)."""
    return [t.lower() for t in _TOKEN_SPLIT_RE.split(message or "") if t]


def _matches_marker(tokens: Sequence[str], marker: str) -> bool:
    """Token-prefix match; markers shorter than 4 chars must equal a token."""
    if len(marker) < 4:
        return marker in tokens
    return any(t.startswith(marker) for t in tokens)


def classify_intent(message: str) -> str:
    """Classify the turn's intent for memory routing (deterministic, no LLM).

    Returns one of :data:`INTENTS`; ``"general"`` when no marker fires.
    """
    tokens = _message_tokens(message)
    if not tokens:
        return "general"
    for intent, markers in _INTENT_MARKERS:
        if any(_matches_marker(tokens, m) for m in markers):
            return intent
    return "general"


# ---------------------------------------------------------------------------
# Memory Scorer — weighted candidate scoring
# ---------------------------------------------------------------------------


class MemoryOrchestratorConfigError(ValueError):
    """Unusable supplied retrieval configuration, fatal only at startup."""


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
        if cfg is None:
            return base
        if not isinstance(cfg, Mapping):
            raise MemoryOrchestratorConfigError(
                "memory.orchestrator.weights must be a mapping; set weights to a mapping "
                "of numeric scoring weights or omit it for defaults"
            )
        kwargs: Dict[str, float] = {}
        for key in cls._FIELDS:
            if key in cfg:
                try:
                    value = float(cfg[key])
                    if isinstance(cfg[key], bool) or not math.isfinite(value) or value < 0:
                        raise ValueError("not a finite nonnegative weight")
                except (TypeError, ValueError, OverflowError) as exc:
                    raise MemoryOrchestratorConfigError(
                        f"memory.orchestrator.weights.{key} must be a finite nonnegative number; "
                        f"set {key} to a finite number >= 0 or omit it for the default"
                    ) from exc
                kwargs[key] = value
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


def rank_candidates(
    candidates: List[Dict[str, Any]], nq: "NormalizedQuery",  # type: ignore[name-defined]
) -> List[Dict[str, Any]]:
    """Relevance-dominant ordering for the per-turn context pack (Gate 1 §4.2).

    One lexicographic comparator — type/importance NEVER cross a relevance
    class boundary, closing the displacement defect where an irrelevant
    decision outranked a topically-exact fact by weight alone:

    ``match_class DESC (3 phrase | 2 all-concepts | 1 any) →
    matched_term_ratio DESC → bm25 ASC (neutral 0 when absent) →
    type_tiebreak DESC → importance DESC → updated_at DESC → id ASC``

    Admission: ``match_class == 0`` (no normalized concept matched) never
    enters the pack — a zero-relevance candidate cannot ride in on
    importance or type bonuses.
    """
    ranked: List[Tuple[Tuple, Dict[str, Any]]] = []
    for cand in candidates:
        match_class, ratio = match_normalized(nq, str(cand.get("content") or ""))
        if match_class <= 0:
            continue
        type_tiebreak = DECISION_VALUE_BY_TYPE.get(str(cand.get("type") or ""), 0.2)
        try:
            importance = max(0.0, min(1.0, float(cand.get("importance") or 0.0)))
        except (TypeError, ValueError):
            importance = 0.0
        ts = _parse_ts(cand.get("updated_at"))
        ts_ord = ts.timestamp() if ts is not None else 0.0
        try:
            bm25 = float(cand.get("_bm25") or 0.0)
        except (TypeError, ValueError):
            bm25 = 0.0
        key = (
            -match_class,
            -ratio,
            bm25,              # ASC inside a DESC tuple: lower bm25 sorts first
            -type_tiebreak,
            -importance,
            -ts_ord,
            str(cand.get("id") or ""),
        )
        ranked.append((key, cand))
    ranked.sort(key=lambda pair: pair[0])
    return [cand for _key, cand in ranked]


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
# Route plans — what the Router fetches per intent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutePlan:
    """Per-intent retrieval plan (the Router's decision output)."""

    #: Always include the most recent active decisions/constraints — these
    #: are the "don't re-walk rejected ground" backbone. Off for casual
    #: questions where recency of decisions rarely matters to the answer.
    include_recent_standing: bool
    search_limit: int
    recent_limit: int


ROUTE_PLANS: Dict[str, RoutePlan] = {
    "project_work": RoutePlan(include_recent_standing=True, search_limit=30, recent_limit=8),
    "debugging": RoutePlan(include_recent_standing=True, search_limit=30, recent_limit=6),
    "user_question": RoutePlan(include_recent_standing=False, search_limit=20, recent_limit=0),
    "general": RoutePlan(include_recent_standing=False, search_limit=25, recent_limit=0),
}

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


# ---------------------------------------------------------------------------
# Context Pack Builder + orchestrator
# ---------------------------------------------------------------------------


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
    by_type: Dict[str, List[str]] = {}
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


def fit_entries_within_budget(
    scored: Sequence[Tuple[Mapping, Any]],
    budget: int,
    *,
    max_entries: int,
    used_start: int = 0,
    measure: Optional[Callable[[Sequence[Tuple[Mapping, Any]]], int]] = None,
) -> Tuple[List[Tuple[Mapping, Any]], int]:
    """Greedy token-budget cut over PRE-SORTED ``(entry, score)`` pairs.

    The bus keeps its content + 8 estimate. Rendered callers supply
    ``measure`` to count the entire trial selection, including its envelope,
    section headers and provenance; records are admitted whole, never truncated.
    An entry that would overflow the remaining budget is SKIPPED (smaller
    ones further down may still fit — one huge entry must not eat the pack);
    ``max_entries`` caps the count; ``used_start`` offsets the budget with
    the caller's already-reserved overhead. Returns ``(selected, used)`` —
    ``used`` is the offset plus the measured selection or estimated entry costs.
    """
    selected: List[Tuple[Mapping, Any]] = []
    used = max(0, int(used_start))
    for row, score in scored:
        if len(selected) >= max(0, int(max_entries)):
            break
        trial = selected + [(row, score)]
        trial_used = (
            max(0, int(used_start)) + measure(trial) if measure is not None
            else used + estimate_tokens_rough(str(row.get("content") or "")) + 8
        )
        if trial_used > int(budget):
            continue
        selected.append((row, score))
        used = trial_used
    return selected, used


class MemoryOrchestrator:
    """Query-aware retrieval over the built-in typed store (Phase 2).

    Built once at agent init (see :func:`build_memory_orchestrator`); each
    turn the conversation prologue calls :meth:`build_pack` with the clean
    user message and injects the result (when non-empty) into the API copy
    of that message as a separate context slot.
    """

    def __init__(
        self,
        store: Any,
        *,
        targets: Sequence[str] = ("memory", "user"),
        token_budget: int = 2500,
        max_entries: int = 20,
        weights: Optional[ScoringWeights] = None,
    ):
        self._store = store
        self._targets: Tuple[str, ...] = tuple(t for t in targets if t in ("memory", "user")) or ("memory",)
        self._token_budget = max(0, int(token_budget))
        self._max_entries = max(1, int(max_entries))
        self._weights = weights or ScoringWeights()

    @property
    def weights(self) -> ScoringWeights:
        return self._weights

    @property
    def token_budget(self) -> int:
        return self._token_budget

    def build_pack(self, message: str) -> str:
        """Route → retrieve → score → budget → render. ``""`` when nothing to add.

        Failures are logged and swallowed: memory retrieval must never break
        a conversation turn.
        """
        try:
            return self._build_pack(message)
        except Exception as exc:  # non-fatal by contract
            logger.warning("memory orchestrator: pack build failed: %s", exc)
            return ""

    def _log_recall(self, *, intent: str, query: str, before: int, after: int, nonempty: bool) -> None:
        """Recall-audit hook (P3). Duck-typed + best-effort: stores without
        ``log_recall`` (legacy flat-file) and failures are silently fine."""
        log = getattr(self._store, "log_recall", None)
        if log is None:
            return
        try:
            log("auto-pack", intent, _message_tokens(query)[:8], before, after, nonempty)
        except Exception as exc:
            logger.debug("memory orchestrator: recall log failed: %s", exc)

    def _build_pack(self, message: str) -> str:
        if not self._token_budget:
            return ""
        query = (message or "").strip()
        if not query:
            return ""
        intent = classify_intent(query)
        plan = ROUTE_PLANS.get(intent, ROUTE_PLANS["general"])
        query_tokens = _message_tokens(query)

        candidates: Dict[str, Dict[str, Any]] = {}

        def _collect(rows: Iterable[Any]) -> None:
            for row in rows:
                row = dict(row)
                if row.get("target") not in self._targets:
                    continue
                candidates.setdefault(str(row.get("id")), row)

        # Layer 1: lexical search (FTS5 with LIKE fallback — store-internal).
        # One NormalizedQuery feeds BOTH the candidate search and the
        # relevance ranking — no second tokenization downstream (Gate 1 §4.2).
        nq = self._store.normalized_query(query)
        _collect(self._store.recall_candidates(query, limit=plan.search_limit, nq=nq))

        # Layer 2 (Router): recent standing decisions/constraints for
        # work/debugging intents — the anti-circular backbone.
        if plan.include_recent_standing:
            _collect(
                self._store.recent_entries(
                    types=("decision", "constraint"),
                    limit=plan.recent_limit,
                )
            )

        if not candidates:
            # An empty funnel is itself the metric ("knew but stayed silent"
            # candidates come from here) — log every exit, not just success.
            self._log_recall(intent=intent, query=query, before=0, after=0, nonempty=False)
            return ""

        # The frozen snapshot already carries these entries in the system
        # prompt — the pack is a supplement, never a duplication.
        already_prompted: Set[str] = self._store.snapshot_contents()
        deduped = [
            row for row in candidates.values()
            if row.get("content") not in already_prompted
        ]
        # Gate 1 relevance ranking is the admission filter and the outermost
        # ordering boundary: match_class==0 never enters, and a lower class
        # can never outrank a higher one. Within each eligible class, the
        # configured weighted score determines both pack order and which
        # entries reach the token-budget cut. Stable sorting preserves
        # rank_candidates' deterministic tie-break order.
        ranked = rank_candidates(deduped, nq)
        now = datetime.now(timezone.utc)
        scored: List[Tuple[Dict[str, Any], float]] = [
            (row, score_candidate(row, query_tokens, self._weights, now))
            for row in ranked
        ]
        scored.sort(
            key=lambda pair: (
                -match_normalized(nq, str(pair[0].get("content") or ""))[0],
                -pair[1],
            )
        )
        if not scored:
            self._log_recall(intent=intent, query=query, before=len(candidates), after=0, nonempty=False)
            return ""

        # Measure complete trial packs: metadata/provenance and the envelope
        # cannot be represented by a fixed per-record overhead.
        selected, used = fit_entries_within_budget(
            scored,
            self._token_budget,
            max_entries=self._max_entries,
            measure=lambda entries: estimate_tokens_rough(render_pack(entries, intent)),
        )
        if not selected:
            self._log_recall(intent=intent, query=query, before=len(candidates), after=0, nonempty=False)
            return ""

        pack = render_pack(selected, intent)

        # One INFO line per non-empty pack: the pack is injected into the
        # API copy of the user message only (never persisted), so this log
        # is the primary live-E2E evidence that the channel fired.
        logger.info(
            "memory orchestrator: context pack intent=%s entries=%d tokens~%d",
            intent, len(selected), used,
        )
        self._log_recall(
            intent=intent, query=query,
            before=len(candidates), after=len(selected), nonempty=True,
        )

        # Usage signal for future scoring/consolidation (best-effort).
        try:
            self._store.bump_access([str(row.get("id")) for row, _ in selected])
        except Exception as exc:
            logger.debug("memory orchestrator: access bump failed: %s", exc)

        # NOTE (2026-08-30 graph TZ): the per-turn pack deliberately does NOT
        # inject a "choice tension" section. The lexical matcher is
        # suggest-only until it proves precision on live data; explicit
        # memory(action=read) results and `hermes memory report` carry the
        # possible-tension evidence where a human or the model can inspect it.
        return pack


def read_memory_boolean_section(mem_config: Mapping, section: str, *, default: bool) -> bool:
    """Absent sections/flags keep defaults; explicit shapes and values are strict."""
    if not isinstance(mem_config, Mapping):
        raise MemoryOrchestratorConfigError(
            "memory must be a mapping; set memory to a mapping or omit it"
        )
    cfg = mem_config.get(section, {})
    if not isinstance(cfg, Mapping):
        raise MemoryOrchestratorConfigError(
            f"memory.{section} must be a mapping; set {section} to a mapping or omit it"
        )
    value = cfg.get("enabled", default)
    if not isinstance(value, bool):
        raise MemoryOrchestratorConfigError(
            f"memory.{section}.enabled must be a boolean (true or false), not {type(value).__name__}; "
            f"set enabled to true or false or omit it for default {str(default).lower()}"
        )
    return value


def read_orchestrator_config(mem_config: Mapping) -> Tuple[int, int, ScoringWeights]:
    """Read the retrieval settings shared by the pack and delegation bus.

    Absent keys retain defaults; explicitly supplied unusable values do not.
    Numeric strings remain accepted, and weights need not sum to one.
    """
    read_memory_boolean_section(mem_config, "orchestrator", default=True)
    cfg = mem_config.get("orchestrator", {})
    if not isinstance(cfg, Mapping):
        raise MemoryOrchestratorConfigError(
            "memory.orchestrator must be a mapping; set orchestrator to a mapping or omit it"
        )
    limits = []
    for key, default, minimum in (("token_budget", 2500, 0), ("max_entries", 20, 1)):
        value = cfg.get(key, default)
        try:
            if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
                raise ValueError("not an integer")
            parsed = int(value)
            if parsed < minimum:
                raise ValueError("below minimum")
        except (TypeError, ValueError, OverflowError) as exc:
            raise MemoryOrchestratorConfigError(
                f"memory.orchestrator.{key} must be an integer >= {minimum}; "
                f"set {key} to an integer >= {minimum} or omit it for default {default}"
            ) from exc
        limits.append(parsed)
    if "weights" in cfg and not isinstance(cfg["weights"], Mapping):
        raise MemoryOrchestratorConfigError(
            "memory.orchestrator.weights must be a mapping; set weights to a mapping or omit it"
        )
    return limits[0], limits[1], ScoringWeights.from_config(cfg.get("weights"))


def build_memory_orchestrator(
    store: Any,
    mem_config: Mapping,
    *,
    memory_enabled: bool,
    user_profile_enabled: bool,
) -> Optional[MemoryOrchestrator]:
    """Factory used by agent init: ``None`` when disabled or not a v2 store.

    Kept as a standalone function so wiring is unit-testable without
    constructing a full ``AIAgent``. Duck-types the store (checks the
    orchestrator-facing methods) instead of importing MemoryStoreV2 —
    the legacy flat-file store simply yields ``None``.
    """
    enabled = read_memory_boolean_section(mem_config, "orchestrator", default=True)
    if store is None or not all(
        hasattr(store, m) for m in ("recall_candidates", "recent_entries", "snapshot_contents", "bump_access")
    ):
        return None
    if not enabled:
        return None
    targets = [t for t, on in (("memory", memory_enabled), ("user", user_profile_enabled)) if on]
    if not targets:
        return None
    token_budget, max_entries, weights = read_orchestrator_config(mem_config)
    return MemoryOrchestrator(
        store, targets=tuple(targets), token_budget=token_budget,
        max_entries=max_entries, weights=weights,
    )
