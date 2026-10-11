# SQLite V2 as the canonical memory store

Status: accepted

Интегрируем архитектуру памяти из форка Architecture 2.0 в локальный форк Hermes, но без переноса форка целиком: происхождение — v0.16.0 (4e9608fc), переносимые файлы — аудитированные версии из 0c76ec28 с перечислением включённых последующих fixes. Каждый профиль получает собственную SQLite-базу (memory.db в HERMES_HOME) как единственный источник истины; MEMORY.md/USER.md становятся производными читаемыми проекциями, пересоздаваемыми после каждой мутации; installer больше не копирует USER.md поверх проекции, а идемпотентно импортирует управляемые записи в SQLite; миграция существующих §-записей одноразовая, с migration manifest; включение — профильный backend flag (default legacy, порядок: тестовая копия → main → design); rollback выполняет проверяемый downgrade export перед возвратом на legacy.

**Considered options:**
- Оставить flat-файлы canonical и прикрутить поиск: отклонено — типизированные статусы, FTS5, провенанс и связи пересмотра требуют структурированного хранилища; у форка уже есть проверенная тестами реализация.
- Перенести форк целиком: отклонено — 2700+ файлов и посторонние подсистемы (kanban, mailbox, auth) заменили бы собственные гарантии этого репозитория (threat scanning, write approval, атомарные batch-и, изоляция профилей).
- Полный event sourcing: отклонено для этого этапа — supersede/deprecate с провенансом покрывает историю решений; hard delete остаётся только для явного удаления мусора.

**Consequences:** ручные правки MEMORY.md/USER.md перезаписываются при следующей записи (осознанно, задокументировано); меняется обработка memory-файлов installer-ом; char limits ограничивают prompt-снапшот, а не хранилище — записи сверх снапшота остаются доступными в SQLite для поиска.

## Provenance (ticket #3, 2026-10)

Перенесённые файлы (source: Architecture 2.0 fork, HEAD `0c76ec28`):

| Файл в workspace | sha256 источника | Замечания |
|---|---|---|
| `agent/memory_store_v2.py` | `32f3a9016211c6c356ca790ab837f7ba8b4d5d696d00db5f6bcc3b3cdbff3095` | адаптирован: parent-import → `tools.memory_tool_store`, per-target flags, `matched_entry`-пиннинг, `resolve_entry`/`resolve_batch_entries`, минимальная per-op делегация `apply_batch` (атомарность — ticket #5) |
| `tests/agent/test_memory_store_v2.py` | `f56fe4cf4bc3d204698efe7a588fe350f7e20c0d70174ffe305f25039213078e` | расширен workspace-контрактами (backend flag, HERMES_HOME/integrity, FTS-fallback, проекции, per-target flags) |
| `tests/agent/test_memory_graph_integrity.py` | `16fd3038739af4f7d51996746d87117810b51f9ca434678653d1b0c58e1f2428` | перенесён без изменений |

Файлы форка не несут per-file заголовков (grep «Dmitry Antipin» по `*.py` = 0 файлов; авторство только в LICENSE строка 3 и FORK.md) — MIT-заголовки и строка copyright добавлены в перенесённые файлы нами, как и требует спецификация.

Fork-specific v2 fixes, включённые в порт (audit range `git log 4e9608fc..0c76ec28`):

1. `faa9d0a2a` fix(memory): Gate 0.5+1 — separate the three memory axes (Н-1A memory repair)
2. `182f63375` fix(memory): cross-target id resolution — the 'read sees it, write can't' loop
3. `87f0524f9` fix(memory): live-acceptance fixes — prefix id resolution + explainable tension growth
4. `56623c3dd` feat(memory): revive the memory graph — schema v4, atomic supersede, safe matcher
5. `ad9d0b4ae` feat(memory): tension map — choice memory as first person (Task 2, over P1)
6. `2eafa93e8` fix(memory): v2→v3 migration must fold the FTS index — 'rebuild' bypasses triggers
7. `afede1b86` feat(memory): P7 — fold ё→е across the search layer (week-1 finding)
8. `2f4c8790e` feat(memory): document supersedes marker (unblock P1) + Phase-4 P2 alias layer
9. `7e79f11b0` docs(memory): schema states eviction is automatic — never archive-and-delete for space
10. `bfce7e448` feat(memory): Phase-4 P1 link-aware recall, P6 eviction demotion, P3 recall-audit log
11. `f2471ba8c` fix(memory): Phase-4 retrieval + honest write telemetry (live-incident fixes)
12. `52cfd065e` fix(tools): memory write gate, whisper pin, upscale policy, host-native test fixes
13. `0aa49b1db` merge: re-integrate upstream/main (13ce0c5c6) — true merge, restores ~15k lost upstream symbols

Коммиты 41–80 audit-диапазона предшествуют v1.1 и уже поглощены собственной линией workspace-форка (spot-check: `#42405` consolidation cap, `#48507` batch, `#26045` drift guard — все присутствуют в workspace-файлах); учтены как provenance, а не как задачи.

Backend-флаг: `memory.backend: file|sqlite_v2` (default `file`, дефолт в `hermes_cli/config_defaults.py`); единственный резолвер `tools.memory_tool.resolve_memory_backend` используется `agent_init._init_memory` и `load_on_disk_store`; неизвестное значение = legacy `file`, без ошибок.

## Downgrade

Откат на legacy — двухуровневый, проверяемый:

1. **Экспорт.** `python scripts/memv2_downgrade_export.py --home <HERMES_HOME>` (предпросмотр — `--dry-run`) выгружает видимые записи canonical store (status active/pinned, без awareness-телеметрии) в §-файлы MEMORY.md/USER.md с проверкой количества (expected == written в отчёте), бэкапом существующих файлов (`.bak.<ts>`) и аудиторным маркером `memories/downgrade-export-report.json`; memory.db не открывается на запись (sha256 до/после в отчёте). Отчёт дополнительно содержит `post_cutover` по каждой цели — число записей, созданных ПОСЛЕ `meta['legacy_migrated']` (момент cutover). Это только наблюдаемость: сам экспорт остаётся ПОЛНЫМ (full-store) намеренно — flat-стор не знает про cutover и должен прочитать каждую видимую запись, а частичный экспорт молча потерял бы pre-cutover legacy-данные, которые оператор ожидает в MEMORY.md/USER.md.
2. **Возврат флага.** В config.yaml профиля — `memory.backend: file` (или удалить ключ): агент стартует на flat MemoryStore и читает экспортированные §-файлы; записи, созданные в V2 после cutover, видны без потерь.
3. **Проверка.** Скрипт печатает JSON-отчёт и возвращает exit 0 только при ok по всем целям; memory.db остаётся на диске — повторный cutover мигрирует по-прежнему идемпотентно (manifest) и видит экспортированные записи как дубли (пропуск с причиной в manifest).
