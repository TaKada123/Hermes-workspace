# Native AG2 channels with externally owned Hermes execution

Status: accepted

Existing Hermes specialists communicate through AG2 Network, while authenticated Hermes Runs execute against profile-owned permanent sessions. AG2 owns channel protocol/history; a small bridge owns delivery reconciliation and session mappings, not memory or model execution. This avoids importing evolving Hermes internals and preserves live profile semantics when checkout/live memory versions differ.

The rejected alternative was embedding a fresh AIAgent in the bridge: it would duplicate profile scoping, configuration, history restoration, approvals and rotation. AG2 default LLM handlers are also excluded. Native AG2 lacks execution deduplication and the owner accepted holding uncertain interrupted work instead of automatically repeating possible side effects.
