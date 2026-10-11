# MEM-V2 integration report — acceptance evidence (ticket #12)

Status: **canonical default-discovery Linux CI PASS; separate MEM-V2 E2E/local gates PASS; live cutover PENDING.**

Актуальная приёмочная точка: source candidate `57a309a6bab854b83ad52cc322dabf9c4c6844a4`, CI head `1b3394851c0f241ed07422af6cc7d0e749ff1acc`. [Run 38137820585](https://github.com/TaKada123/Hermes-workspace/actions/runs/38137820585): 20/20 jobs success, **5335 файлов, 57577 passed, 0 failed, 763 skipped, 1 xfailed, 0 xpassed, 0 collection errors, 0 retries**. Измерения, ограничения и источники — §7; эти результаты заменяют прежний full-suite blocker, но не означают live rollout или полное покрытие всех платформ.

**Следующий шаг:** проверить/apply только documentation commit в изолированной интеграционной ветке; затем отдельно согласовать публикацию PR и merge. Issues #2–#12 остаются открытыми до выполнения live cutover criteria. В этом acceptance-этапе source/tests/workflows и ADR не изменяются, тесты/review повторно не запускаются, live homes и действующие процессы не затрагиваются.

Ниже, до §7, сохранён исторический отчёт copy-validation и первоначальных прогонов. Это не новая проверка актуального candidate и не подтверждение состояния live homes сейчас; перечисленные там риски — исторические наблюдения, без нового code review.

Historical copy-validation status: **validated on state-copies of both real profile homes; downgrade round-trip proven; real homes untouched during that run.**

- Copy validation: MAIN (default) — full installer/verifier/manifest/recall/agent-smoke sequence green.
- Copy validation: DESIGN — flag-flip cutover, migration 7/7, recall + agent smoke green (verifier is Main-only by design — see §5).
- Downgrade export + rollback to legacy: green on the MAIN copy; exported MEMORY.md byte-identical to the real pre-cutover file.
- Real homes: 1208/1208 copied files re-hashed after the run — all unchanged.
- Historical full `scripts/run_tests.sh` run: completed, but **not green**; classification is retained in §6. This historical blocker is superseded by the measured canonical CI evidence in §7, not by a claim that the old run succeeded.

All commands ran with the repo's test venv python (`.../installs/7d27e89e058145aa/test-environment/gen-61e60788dcb64beeaab611091e631020/venv/bin/python`), `HERMES_HOME` pointing at the copies, `HOME=/tmp/hh-cutover/fakehome`, never `scripts/setup-hermes.sh`. Copies live under `/tmp/hh-cutover/` (`main-home`, `main-home-control`, `design-root/profiles/design` — the design copy mirrors the real profile layout `<root>/profiles/design`, which is how `hermes_cli/profiles.py::get_profile_dir` resolves the design HERMES_HOME).

---

## 1. Что перенесено

Из форка Architecture 2.0 (dmantipinai-hash fork, HEAD `0c76ec28`; базис аудита `4e9608fc` = v0.16.0) перенесены только компоненты памяти; форк целиком не переносился (2700+ файлов, посторонние kanban/mailbox/auth/awareness). Происхождение и пофайловые sha256 источников зафиксированы в `docs/adr/0001-sqlite-v2-canonical-memory-store.md` (Provenance):

| Компонент | Файл | sha256 источника (0c76ec28) |
|---|---|---|
| Typed SQLite canonical store | `agent/memory_store_v2.py` | `32f3a9016211c6c356ca790ab837f7ba8b4d5d696d00db5f6bcc3b3cdbff3095` |
| Orhestrator + context pack | `agent/memory_orchestrator.py` | `541efc1082faba3856e6e79207ed6cd129e65d09991fb8618de50f321c934b92` |
| MemoryBus | `agent/memory_bus.py` | `47130d024005938856c69b16155a19085450c7bf29709b531c7d4ef0fd59a788` |
| Тесты store v2 | `tests/agent/test_memory_store_v2.py` | `f56fe4cf4bc3d204698efe7a588fe350f7e20c0d70174ffe305f25039213078e` |
| Тесты graph integrity | `tests/agent/test_memory_graph_integrity.py` | `16fd3038739af4f7d51996746d87117810b51f9ca434678653d1b0c58e1f2428` |

Плюс портированные тесты оркестратора/шины, миграции, E2E context-pack/изоляции профилей/briefing (`tests/agent/test_memory_orchestrator.py`, `test_memory_bus.py`, `test_memory_store_v2_migration.py`, `test_memory_pack_injection.py`, `tests/e2e/core/memv2/*`) и новая работа без аналога в форке: migration manifest (#4), downgrade export (#11, `agent/memory_downgrade.py` + `scripts/memv2_downgrade_export.py`), idempotent installer import (#9).

Лицензия/авторство: файлы форка не несут per-file заголовков (grep «Dmitry Antipin» по `*.py` = 0; авторство — только LICENSE строка 3 и FORK.md). MIT-заголовки и строка copyright Dmitry Antipin добавлены в перенесённые файлы нами (требование спецификации); provenance — в ADR-0001.

Fork-specific v2 fixes, включённые в порт (audit `git log 4e9608fc..0c76ec28`): `faa9d0a2a` Gate 0.5+1, `182f63375` cross-target id resolution, `87f0524f9` prefix id resolution, `56623c3dd` schema v4 + atomic supersede, `ad9d0b4ae` tension map, `2eafa93e8` FTS fold on v2→v3 migration, `afede1b86` ё→е folding (P7), `2f4c8790e` supersedes marker + alias layer, `7e79f11b0` eviction doc, `bfce7e448` Phase-4 link-aware recall + recall log, `f2471ba8c` Phase-4 retrieval, `52cfd065e` write-gate fixes, `0aa49b1db` upstream re-integration. Коммиты 41–80 диапазона предшествуют v1.1 и уже поглощены собственной линией workspace-форка (spot-check #42405/#48507/#26045 — присутствуют).

## 2. Что адаптировано

- **Backend flag**: `memory.store_v2: bool` (arch2, default true) → `memory.backend: file|sqlite_v2` (default `file` = legacy). Один резолвер `tools.memory_tool.resolve_memory_backend` используется `agent_init._init_memory`, `load_on_disk_store`, installer и verifier; неизвестное значение = legacy без ошибок.
- **Собственные гарантии сохранены**: threat scanning (`_scan_memory_content`, strict scope — и на load, и на каждую запись, включая v2 batch pre-scan), write approval (`_apply_write_gate` + staging), background-review gate (unattended review может только `add`; destructive-действия stage-ятся — покрывает v2-действия), атомарный batch (все-или-ничего + `resolve_batch_entries` + `matched_entry`-пиннинг) — arch2-вариант с последовательным batch не переносился.
- **Отдельное право rollback**: в arch2 `bus.rollback` был без capability-чека; добавлены per-target rollback capabilities, `_require_active` на rollback, read-only потребитель получает структурный отказ и на запись, и на rollback (ADR-0002).
- **Субагенты**: `delegation.memory_briefing` gate (arch2 читал top-level `memory_briefing` — баг исправлен); брифинг — одноразовая неизменяемая копия в goal; ребёнок без memory tool/bus handle/пути к БД (DELEGATE_BLOCKED_TOOLS).
- **Installer**: legacy-путь побайтово прежний; на sqlite_v2 — USER.md не копируется, управляемые §-записи импортируются идемпотентно через публичный `MemoryStoreV2.import_managed_entries` (маркер `meta['managed_import_sha:installer']`, claim/deprecate при изменении источника), fail-closed.
- **Verifier**: backend-aware check #2 — на v2 проверяются canonical rows (`visible_rows` + `managed_import_status`), а не проекция.
- **Downgrade export**: новая работа (аналога в arch2 нет) — полный экспорт видимых записей в §-файлы с count verification, `.bak`, аудит-отчётом, memory.db не открывается на запись.

## 3. Как включить

Rollout порядок (по спецификации): **тестовая копия → main (default) → design**. Порядок на каждый профиль:

1. **Снять копию HERMES_HOME** (SOUL.md, memories/, policies/, skills/, plugins/, config.yaml, .env, pending/) и прогнать на ней последовательность из §6 — не на живом профиле.
2. **Флаг**: в `config.yaml` профиля — `memory: {backend: sqlite_v2}` (эквивалент: `hermes config set memory.backend sqlite_v2`). Одноразовая миграция и manifest выполнятся при первом старте агента с этим бэкендом.
3. **Main**: при необходимости — `HERMES_HOME=<home> python scripts/install_gumar_runtime.py` (на v2 управляемый USER.md импортируется в SQLite; файлы не затираются). **НЕ запускать legacy-инсталлер после того, как агент жил на файлах** — он перезапишет живые правки USER.md (см. §5/§6, замечено на копии).
4. **Design**: только флаг. `scripts/install_gumar_runtime.py` на design-доме запускать **запрещено** — он заменяет design SOUL.md/USER.md на Main-версии (измерено на копии, §6). Управление design-домом остаётся за `scripts/install_design_profile.py`.
5. Проверка: `HERMES_HOME=<home> python scripts/verify_gumar_runtime.py` — строка `USER.md: sqlite_v2 canonical store rows + projections OK`.

## 4. Как откатить

Двухуровневый откат (memory.db всегда остаётся на диске):

1. **Экспорт**: `python scripts/memv2_downgrade_export.py --home <HERMES_HOME>` (предпросмотр — `--dry-run`). Экспортирует видимые записи (active/pinned) в §-файлы MEMORY.md/USER.md, создаёт `.bak.<ts>`, пишет `memories/downgrade-export-report.json`; exit 0 только при `ok: true` по всем целям; memory.db не модифицируется (sha256 до/после в отчёте).
2. **Возврат флага**: `memory.backend: file` (или удалить ключ) — агент читает экспортированные §-файлы через legacy MemoryStore; записи, созданные после cutover, видны без потерь (`post_cutover` — наблюдаемость в отчёте).
3. **Проверка**: `scripts/verify_gumar_runtime.py` — строка `USER.md: native MemoryStore prompt snapshot OK`.
4. Повторный cutover идемпотентен: manifest-миграция пропускает уже экспортированные записи как дубли (с причиной в manifest).

Проверено на копии: экспортированный MEMORY.md **побайтово совпал** с реальным pre-cutover MEMORY.md; см. §6.

## 5. Оставшиеся проблемы и риски

1. **§-делимитер в контенте** (downgrade export): экспорт join-ит записи через `ENTRY_DELIMITER` («§») сырым контентом; запись, содержащая «§», при re-parse даст больше записей, чем expected → `ok: false`, exit 1. Fail-closed (потеря невозможна, экспорт детектит расхождение), но откат требует ручной чистки такой записи.
2. **Recall-log по умолчанию выключен**: `config_defaults.py` — `recall_log: {enabled: False}`. Recall-аудит (`recall_log_summary`, `hermes memory report`) не пишется, пока не включить `memory.recall_log.enabled`.
3. **Drift-guard семантика меняется на v2** (осознанно, ADR-0001): на legacy внешние правки MEMORY.md/USER.md защищены drift guard (#26045, отказ записи при расхождении); на v2 проекции — производные, ручные правки перезаписываются следующей мутацией. Пользовательские правки файлов на v2 должны идти через memory tool.
4. **Projection race между двумя инстансами store**: проекции переписываются после каждой мутации; два одновременных процесса с одним HERMES_HOME — last-writer-wins, проекция может отставать от canonical rows. Verifier это учитывает (читает canonical rows, от проекций требует только существование), но операционно: во время cutover writers в БД писать не должны (спецификация) — не запускать двух агентов на одном home одновременно.
5. **Per-turn pack latency**: оркестратор строит pack каждый ход (SQLite-запросы + скоринг + render); на копии реальных данных pack составил 480 токенов (main) / 291 токен (design). Приемлемо, но это постоянная прибавка к каждому ходу на v2 (смягчается token budget 2500 и дедупликацией против снапшота).
6. **Main-installer на design-доме — footgun** (измерено, §6): `install_gumar_runtime.py` заменяет design SOUL.md (804cc… → 601172… = Main) и USER.md (b763… → f781… = Main managed). Design cutover — только флаг.
7. **Verifier Main-only**: `verify_gumar_runtime.py` падает на design-доме на check #1 (`Главный Hermes` в SOUL) и требует Main router hint в always-on (на design секция пустая) — это проверка Main-рантайма; design-дом валидируется manifest + recall + E2E (профильная изоляция), а не этим скриптом.
8. **`install_design_profile.py` не backend-aware**: его `_copy_file` продолжит перезаписывать design-проекции MEMORY.md/USER.md (на v2 они производные). Не критично (store пересоздаст проекции), но managed import для design не реализован — возможная future work.
9. **sha memory.db дрейфует между процессами**: первый open в WAL-режиме может чекпоинтить WAL (наблюдено: db3aa5… → 4452e3… между dry-run и real export). Гарантия «экспорт не пишет в БД» — per-run (before==after внутри прогона, проверено); побайтовую стабильность файла БД между процессами ожидать нельзя.
10. **Legacy-инсталлер затирает живые правки USER.md**: прежнее поведение (резерв в backups/), но при cutover на живом профиле сначала флаг+миграция, инсталлер после (контрольный прогон §6 показал: при флаге без legacy-инсталлера мигрировали ВСЕ живые записи — user recognized 2/2, включая агентскую §-запись).

## 6. Результаты валидации

Копии: `/tmp/hh-cutover/main-home` (default), `/tmp/hh-cutover/main-home-control` (контроль: флаг без legacy-инсталлера), `/tmp/hh-cutover/design-root/profiles/design`. Базовая побайтовая сверка копий с оригиналами: **main 569/569, design 639/639 файлов — byte-identical** (sha256).

### MAIN (default), полная последовательность

| Шаг | Команда | Результат |
|---|---|---|
| (a) legacy install | `install_gumar_runtime.py` (HERMES_HOME=main-home) | EXIT 0; 13/14 managed-файлов IDENTICAL оригиналу, config.yaml IDENTICAL; заменён только `memories/USER.md` (живая §-запись «В визуальных проектах…» → managed-копия, backup создан) |
| (b) флаг | `memory.backend: sqlite_v2` в config.yaml | применён |
| (c) v2 install | `install_gumar_runtime.py` повторно | EXIT 0; USER.md **не** в списке установленных; `imported: 0, claimed: 1, deprecated: 0, sha f781eea1ddf3` |
| (d) verifier | `verify_gumar_runtime.py` | EXIT 0; `Gumar runtime verification: OK`; `USER.md: sqlite_v2 canonical store rows + projections OK`; combined prompt 6399/6800 |
| (e) manifest | `memories/migration-manifest.json` | memory: recognized 5, imported 5, skipped 0 (sha c62858b5f9cc…); user: 1/1/0 (sha f781eea1…); totals 6/6/0; meta: `migration_manifest`, `legacy_migrated`, `managed_import_sha:installer`, schema_version 4 |
| контроль | свежая копия, только флаг + v2-install (реальный порядок cutover) | manifest: memory 5/5/0, user **2/2/0** (живой sha 98f1ae7632e7 — обе записи, включая агентскую), totals **7/7/0**; `imported: 0, claimed: 1, deprecated: 0` |
| (f) recall | MemoryStoreV2 на контрольной копии | visible: memory 5, user 2; `recall('memory','как оценить стоимость токенов prompt-size')` → 3 строки, в т.ч. id `6ad9e94e` «Sizing Hermes prompt cost: `hermes prompt-size` prints BYTES…»; `recall('user','референсы визуальных проектов…')` → 2 строки, в т.ч. id `a7822b15` «В визуальных проектах пользователь ожидает…» |
| (g) agent smoke | AIAgent + FakeLLMServer (scripted memory read turn + relevant turn) | orchestrator wired; оба хода ok; S1 snapshot: «- ОС: EndeavourOS на базе Arch Linux.»; S2 pack: `## Retrieved memory — this turn (480 tokens)` с реальной записью `6ad9e94e` (status/id/date цитируются); S4 история без pack |

### DESIGN (flag-flip cutover)

| Шаг | Результат |
|---|---|
| Footgun-демо | Main-installer на design-доме: SOUL.md 804cc…→601172… (Main), memories/USER.md b763…→f781… (Main managed), config.yaml изменён. Копия восстановлена — **этот путь для design запрещён** |
| cutover | только `memory.backend: sqlite_v2`; миграция при первом открытии store |
| manifest | memory: recognized 6, imported 6, skipped 0 (sha 9f1c9c59…); user: 1/1/0 (sha b763ecf2…); totals **7/7/0** |
| on-demand файлы | `memories/design/{global,references,projects}.md` — IDENTICAL (не тронуты) |
| recall | `recall('memory','как хранить контекст проектов дизайн')` → design/references `8fca7c1f`, design/systems `45948081`, design/projects `047672a8`; `recall('user','как обращаться к пользователю')` → `6439a487` «Пользователь предпочитает русский язык, обращение „Би“…» |
| agent smoke | S1 snapshot: «# Design Agent» + «Пользователь предпочитает русский язык»; S2 pack: `## Retrieved memory — this turn (291 tokens)` с design/systems `45948081` и design/global `8381762e`; S4 pack-free |
| verifier | EXIT 1 на check #1 («Главный Hermes» в SOUL) — Main-only скрипт, ожидаемо (см. §5.7); backend-aware логика design-дома проверена manifest/recall/smoke |

### Downgrade round-trip (main-home)

| Шаг | Команда | Результат |
|---|---|---|
| dry-run | `memv2_downgrade_export.py --home main-home --dry-run` | EXIT 0; memory expected 5, user expected 1; db unchanged |
| export | `memv2_downgrade_export.py --home main-home` | EXIT 0; memory `expected 5, written 5, ok: true`; user `1/1, ok: true`; `.bak.1791567306` оба; memory.db sha 4452e3… unchanged; audit `downgrade-export-report.json` |
| fidelity | diff с реальным pre-cutover | экспортированный MEMORY.md **побайтово равен** `/home/vottak/.hermes/memories/MEMORY.md` |
| rollback | `memory.backend: file` + verifier | EXIT 0; `USER.md: native MemoryStore prompt snapshot OK`; memory.db сохранён |

### Целостность оригиналов

После всех прогонов повторно прохешированы все 1208 скопированных файлов реальных домов: **все хеши совпали с pre-run манифестами — реальные /home/vottak/.hermes и /home/vottak/.hermes/profiles/design не изменены ни на байт.**

### Тесты

Полный `scripts/run_tests.sh` был выполнен лидом с явно заданным `HERMES_PYTHON`, но **не прошёл**. Первоначальный pipeline ошибочно показывал shell exit 0 из-за `2>&1 | tail -40`; сама сводка runner содержала многочисленные падения вне MEM-V2 и collection errors. Три подтверждённых класса причин:

1. Test interpreter находился внутри реального `/home/vottak/.hermes`; `tests/home_io_guard.py` закономерно блокировал обращения к `sys.executable`/installation paths. После reflink-копии venv в `/var/tmp/hermes-memv2-test-venv` файл `tests/hermes_cli/test_update_target_identity.py` стал зелёным: **31/31 passed**.
2. Baseline репозитория уже не самодостаточен для всей обнаруживаемой suite: например, `tests/ci/test_desktop_bundle_smoke.py` требует отсутствующий и в `main` файл `.github/workflows/desktop-bundled-release.yml` (22 падения); `tests/tools/test_fal_sdk.py` не коллекционируется без optional `fal-client`.
3. Несвязанные с MEM-V2 baseline-тесты остаются красными и при вынесенном venv: `tests/hermes_cli/test_profiles.py` — **106 passed, 2 failed, 3 skipped**; `test_web_server_profile_unification.py` — **21 passed, 7 failed** из-за ссылки terminal environment на реальный managed install. Ни один из этих production/test файлов не изменён в `main...mem-v2-integration`.

На момент этого исторического прогона критерий «полный scripts/run_tests.sh зелёный» **не был выполнен**. Последующее CI-доказательство §7 заменяет этот blocker в пределах canonical default-discovery Linux suite; старые падения не переобозначаются как прошедшие. Live cutover и закрытие ticket #12 остаются отдельными незавершёнными действиями.

MEM-V2 gates при этом зелёные:

- full memory/delegate unit battery: **794 passed, 0 failed**;
- MEM-V2 integration E2E: **9 passed, 0 failed**;
- import smoke: **OK**;
- финальный targeted installer/verifier + profile-isolation subset:

```text
scripts/run_tests.sh --include-integration -m integration \
  tests/scripts/test_install_gumar_runtime_v2.py \
  tests/e2e/core/memv2/test_memv2_profile_isolation_e2e.py
```

Результат targeted subset: **2 файла, 13 тестов, 0 failed (100%)** — `test_install_gumar_runtime_v2.py` (8 тестов; контракт installer/verifier на обоих бэкендах, включая idempotent import и backend-aware verifier) + `test_memv2_profile_isolation_e2e.py` (5 тестов; реальные процессы-профили против FakeLLMServer: канареечная изоляция snapshot+pack, SOUL/skills по профилям, persistence через перезапуск процесса, sanctioned design.route, per-profile backend flag).

## 7. Актуальная measured acceptance — 2026-10-11

### CI: полный canonical default-discovery, не все существующие lanes

- Source candidate: `57a309a6bab854b83ad52cc322dabf9c4c6844a4`.
- Tested CI head: `1b3394851c0f241ed07422af6cc7d0e749ff1acc`.
- [Run 38137820585](https://github.com/TaKada123/Hermes-workspace/actions/runs/38137820585), свежий GitHub readback: `completed/success`, **20/20** canonical shard jobs success.
- Source candidate → CI head: изменены **только два CI-файла** — `.github/workflows/memv2-canonical-full-suite.yml`, `scripts/ci/memv2_shards.py`. Production и tests tree идентичны candidate. Это не утверждение о размере всего integration PR относительно main.
- Все 20 artifact ZIP проверены по GitHub SHA-256 digest; union shard lists = canonical set: **5335 уникальных файлов**, без overlap, missing или extra. Сводки прочитаны из `canonical.log`, не из одного зелёного workflow badge.
- Итог: **57577 passed, 0 failed, 763 skipped; 1 xfailed, 0 xpassed; 0 collection errors, 0 retries**. Не считать skips/xfail пройденными тестами.
- Окружение artifact audit: standalone **Python 3.14.7**, **SQLite 3.53.1**, **uv 0.12.3**; test venv и HERMES_HOME вне checkout. Это CI environment, не изменение локального runtime.

Источники: `/var/tmp/hermes-memv2-ci-success-evidence/aggregate-manifest.json`, `artifacts.json`, `memv2-canonical-slice-{1..20}/{result.json,coverage.json,canonical.log,slice-XX.txt}` и audit JSON. Parent независимо запускал `verify-evidence.py`; в acceptance-этапе повторно проверен только этот evidence verifier (не тесты): `verified: true`, totals совпали. Readbacks и сверка готовых локальных логов: `/var/tmp/hermes-memv2-acceptance-report/`.

**Граница покрытия:** canonical runner excludes каталоги `docker`, `e2e`, `integration`; pytest addopts исключают маркеры `integration` и `live`. Linux не выполняет macOS/Windows platform cases. Отдельный MEM-V2 integration E2E ниже закрывает свой конкретный шов, но не все исключённые lanes, не desktop/JS/native matrix и не live provider tests.

**Два compiler/build skip:** `tests/hermes_cli/test_update_finish.py` в shard 4 — **11 passed, 2 skipped**. Source-defined `_npm_graph` требует compiler binaries из checkout `node_modules`; skipped cases: `test_selected_child_builds_and_finalizes_under_parent_lock`, `test_real_compiler_failure_retains_receipt_and_skips_completion`. Это непроверенная build-часть, не PASS. Источники — `source-readbacks/tests/hermes_cli/test_update_finish.py` и shard 4 `canonical.log`. Artifact сохраняет file-level counts, не passed node IDs/полный skip-reason output; именное объяснение основано на source skip condition. Аналогично disk-cleanup: 36 passed/1 macOS-only skip. Остальные 763 skips не выдаются за индивидуально разобранные.

### Отдельные уже выполненные локальные gates candidate

Все числа ниже сверены со сводками готовых логов; новых запусков нет. Источник — `/var/tmp/hermes-memv2-realm-candidate-logs/final-evidence.json` (`merge = 57a309a6bab854b83ad52cc322dabf9c4c6844a4`), рядом `*.command.json` и `*.testlist.json`. Использован canonical `scripts/run_tests.sh`, `-j 2 --file-retries 0`; E2E отдельно с `--include-integration -m integration`. Standalone test environment, isolated HOME/HERMES_HOME, bubblewrap скрывал live home; environment audit до/после: dependencies удовлетворяют lock, mismatch/missing пусты, audit одинаков.

| Gate | Файлы | Passed | Failed | Skipped | Лог в candidate evidence directory |
|---|---:|---:|---:|---:|---|
| Memory/delegate | 82 | 1054 | 0 | 0 | `memory-delegate.log` |
| MEM-V2 process integration E2E | 7 | 75 | 0 | 0 | `memv2-e2e.log` |
| Installer/verifier | 2 | 35 | 0 | 0 | `installer-verifier.log` |
| Prepared/packaging/PM | 11 | 45 | 0 | 2 | `prepared-packaging-pm.log` |
| Journey/render/graph | 3 | 13 | 0 | 0 | `journey-render-graph.log` |
| **Всего отдельных test gates** | **105** | **1222** | **0** | **2** | `final-evidence.json` |

Import smoke: exit 0, `import-smoke.log`; environment audits: exit 0. Не добавлять local totals к CI totals: suites пересекаются. Эти 2 local skips относятся к prepared/packaging/PM gate и не смешиваются с двумя compiler skips в CI.

Ранее падавшие локально файлы в данном CI выполнены без skips: `tests/agent/test_run_agent.py` — **281 passed/0 failed/0 skipped**, shard 5; `tests/gateway/test_clarify_delivery_fallback.py` — **7 passed/0 failed/0 skipped**, shard 7. Источники — соответствующие `canonical.log` и `per_file_results` aggregate manifest. Parent отдельно подтвердил локальные reruns 281/7 с 0 skips; это parent-provided evidence, не новые запуски acceptance-агента и не доказательство зелёного завершения всего локального full-suite процесса. Действующий локальный процесс не остановлен и не изменён.

### Remote main, PR scope и безопасный следующий шаг

Fresh readback remote main: **`5de3bbaeefa64b8c7e4ec1d1631e660e70e3479f`**. Старый локальный baseline `a94ef8fb1273b85312b6272b3f53fcd0a254b1cd` не равен remote main: он на 2 коммита впереди; tree delta включает AGENTS routing, GLOSSARY, два ADR и `docs/agents/*`. Remote main — ancestor CI head, merge-base равен remote main; `main...CI head`: **0 main-only / 83 candidate-only commits**. Divergent main-side изменений и merge conflict по этому snapshot не выявлено; merge/rebase не выполнялись. Перед публикацией/merge требуется повторить main readback, не использовать stale baseline и не терять ADR.

Весь candidate относительно remote main шире memory production: **149 изменённых файлов**, включая upstream-workflow test fixtures, test-environment/runner/packaging support, lock updates и CI. Эти уже существующие изменения не пересматривались и не модифицировались в acceptance-этапе; их нельзя выдавать за «всего два файла» или за documentation-only PR. Новый acceptance commit меняет только этот report; ADR-0001/0002 сохранены.

Открытый PR: [#1](https://github.com/TaKada123/Hermes-workspace/pull/1) — Dependabot `actions/checkout-7`, не MEM-V2. Открытого MEM-V2 PR не найдено; GitHub issues **#2–#12 OPEN**. Draft PR body подготовлен локально, без automatic closing keywords. Публикация, merge и изменение issues в этом этапе не разрешены.

### Live cutover — PENDING

Copy-validation в §6 — исторический prerequisite, не live acceptance. До финального закрытия spec/tickets необходим отдельно разрешённый rollout **fresh copies → default → design**: актуальные backups/manifest, контроль writers и migration integrity/количеств, recall/context-pack/briefing smoke после рестарта, проверяемый downgrade export с post-cutover записью и профильная изоляция. Main installer нельзя запускать на Design home; Main-only verifier не объявлять Design PASS. Разрешение на публикацию/merge не является разрешением менять live homes. До выполнения и записи этих критериев issues остаются открытыми, live backend flags не меняются.
