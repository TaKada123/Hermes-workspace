# Domain map for Main Hermes

Main keeps this routing index; domain procedures, memories and credentials stay with the owning profile.

| Domain | Owner | Main action | Scope |
|---|---|---|---|
| Visual design, websites, presentations, portfolios, branding | `design` | `design.route` | Design profile owns visual decisions and deliverable QA. |
| University coursework and ESU assignments | `university` | Not registered in `action_registry.json` yet | University profile owns ESU assignment rules, course monitor and task content. |
| Software architecture | `architect` | Direct profile entry; no registered route yet | Architecture review and system design. |
| Code implementation | `coding` | Direct profile entry; no registered route yet | Repo-scoped implementation and tests. |
| Cross-domain request | Identify every required expert before execution | Cross-domain collaboration workflow is not implemented yet | Tell the user at the start which experts are needed; do not silently drop one domain or make the user coordinate experts. The experts should share task-specific context, exchange attributed questions/answers, review the same artifact and return a finished result. Ask the user only for genuinely blocking decisions or permissions. |

## Main routing rule

For a single-domain request, hand off the original request and explicit attachments to that domain's owner. Do not duplicate its domain-specific instructions in Main.

For a cross-domain request, announce the participating profiles before work begins. The profiles do not inherit one another's private memories or full session histories; any collaboration system must provide a shared task packet/thread with provenance and durable artifacts. The packet/thread, not Main's private reasoning, carries the shared context.

Current status: `design.route` is implemented. Multi-profile cross-domain classification, direct profile-to-profile message delivery, automatic continuation after a reply, dual acceptance and final-result delivery are design goals only; they are not shipped in this bundle. No agent or user should be told that autonomous cross-domain collaboration is already working.
