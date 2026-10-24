# Проверка результата

## Итог

- Ticket-suite: **11 passed, 0 failed**, 3 test files, canonical `scripts/run_tests.sh`. См. `ticket-suite.log`.
- Real installed-host integration: **1 passed**, fresh installed wrapper + PluginManager + `_collect_pre_llm_call_context` + `compose_user_api_content`, с изолированными temporary home. См. `host.xml`, `host-run.log` и extracted host receipts в `verification.json`.
- Два профиля: общий symlink code, одинаковые session/turn id, независимые 1,2,2,3; дополнительно два managers в одном процессе, регистрация/вызов под разными profile scopes.
- L3 poisoned-config test: auditor none, audit_levels empty, auditor_command empty, 4 incidents с auditor_invoked=false и verdict_received=false, sentinel child не запущен.
- 9 vendored core files byte-for-byte совпали с upstream revision 16927bdbb03cf97dc81d914648cc192fe71201d3 и SHA256 manifest.
- Hash baseline **17345 tracked files/index entries**, `baseline_changes=[]`; существующий dirty tracked tree/index не изменён.
- Ни в одном из пяти live target homes каталог плагина не появился. Live `--apply`, gateway restart, commit не выполнялись.
- Live read-only dry-run: exit 0; default, architect, coding, design, university. См. `live-dry-run.log`.

## Standards (self-review, не независимые subagents)

Источники: root AGENTS.md (prompt-cache, profile islands, no core changes, canonical runner), пользовательский scope, QUALITY_POLICY.md, upstream source/protocol. Проверены только новые owned files, без ревью чужого dirty diff.

Исправлены обнаруженные проблемы: sqlite context manager сам не закрывал connection (добавлен closing); safety overlay сначала сбрасывал upstream session on/off (теперь сохраняются только валидные auto/manual bool, security keys всегда перезаписываются); неправильно предполагалась активация только после restart (прочитан installed activate_plugin_now, описан hot-reload). Controls regression доказан RED → GREEN; red log сохранён отдельно.

Блокирующих Standards замечаний после исправлений нет. Синтаксис проверен write tools и compilation canonical runner. Отдельные ruff/pyright executable в PATH не найдены; полный lint/typecheck монорепозитория не заявляется. Worker импортирует vendored platform_runtime динамически после sys.path binding: статическая диагностика missing import сама по себе не отражает проверенную загрузку runtime.

## Spec (self-review)

Подтверждены input→protocol seam, silent cases, quoted/meta/protocol replay, escalation/reset/manual audit, session/profile isolation, durable dedup/restart/concurrency, fail-open malformed/error/timeout, immutable external-auditor prohibition, pinned provenance и отсутствие live/install/commit changes. Одобрённое уточнение «всем профилям» реализовано discovery + единый code tree + profile-local state.

Открытые ограничения: нет upstream LICENSE (не публиковать vendored code без разрешения); обработка только string input до лимита, не multimodal; at-most-once допускает потерю при crash/timeout после admission; LLM obedience и live canary не проверены. Host policy запрещает аудиторов в тексте протокола, но адаптер не является глобальным sandbox tool calls рабочего агента. Installer enable может hot-reload процессы без restart; multi-profile apply не является одной общей транзакцией. Родитель должен зарегистрировать постоянный action; dirty registry здесь намеренно не тронут.

Итог: Standards — 0 открытых блокеров; Spec — все заявленные acceptance seams проверены, live activation/LLM response остаются за границей этой работы.
