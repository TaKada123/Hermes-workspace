# Changelog

Все существенные изменения конфигурации Hermes фиксируются здесь.

## 1.1.0 — 2026-10-06

- Добавлен отдельный нативный профиль `design`: собственные SOUL, config, sessions, изолированная profile memory и ограниченный design toolset. Профиль не является постоянно запущенным процессом.
- Design Agent назначен ведущим дизайнером/арт-директором и domain orchestrator; Superdesign используется только для исследования концепций, Impeccable — только для critique/audit/polish.
- `engineering-portfolio` оформлен как domain skill Design Agent с зарегистрированными режимами `create`, `extend`, `edit`; для EXTEND Superdesign не вызывается по умолчанию, для тривиального EDIT не вызываются Superdesign и Impeccable.
- В Main оставлен только короткий on-demand `design-router`; крупные design skills отключены в Main и не удалены с диска. Handoff сохраняет исходный user request verbatim и передаёт только явные attachments и минимальный project context.
- Action Registry дополнен стабильной точкой `design.route` (`route_type: profile`, `route_id: design`) и тремя workflow инженерного портфолио. Эта точка совместима с будущим JEV без изменения Design Agent.
- Добавлены установщик и verifier профиля. Большие skill-инструкции остаются on-demand; global policies не дублируются в profile SOUL.

## 1.0.4 — 2026-10-06

- Tool surface сокращён: 7 холодных/условных инструментов уведены в `tools.tool_search.defer` (`skill_manage`, `text_to_speech`, `browser_vault_list`, `browser_vault_fill`, `browser_vault_save_login`, `browser_vault_enter_code`, `browser_vault_unlock`). Результат: 25 → 18 инструментов в обычной CLI-сессии, схемы 44 875 → 35 483 B (−21%), статический префикс дешевле на ≈2 477 токенов (по реальному тарифу $0.15/млн — $0.00037 холодным запросом, $0.00001 из кэша). Все 7 инструментов остаются вызываемыми через Tool Search (проверено поиском, `tool_describe` и реальным `tool_call`).
- Побочный эффект, который пришлось закрыть: Hermes гейтит нативное наставление о скиллах по видимости инструмента (`agent/system_prompt.py:295`, `"skill_manage" in names`), поэтому при defer пропали и `SKILLS_GUIDANCE`, и блок `## Skill Safety Rule`. Оба правила возвращены как два коротких always-on правила в `SELF_IMPROVEMENT.md` (секция «Runtime-правила скиллов») — теперь они живут в политике, а не в промпт-билдере.
- Вторая always-on секция плагина переименована: `gumar.runtime.02-memory` → `gumar.runtime.02-memory-and-skills` (в ней правила памяти, блок скиллов и on-demand индекс). Потолки: 3 900 символов на секцию, 6 800 суммарно.
- Defer закреплён в `scripts/install_gumar_runtime.py` (`REQUIRED_DEFER`): установщик восстанавливает список при каждом запуске и сохраняет имена, добавленные вручную. Важно: `tools.tool_search.defer` — явный список, который заменяет курируемый набор Hermes, поэтому курируемые 17 имён повторены в `REQUIRED_DEFER`; холодные инструменты, добавленные в будущих версиях Hermes, автоматически дефериться не будут (список надо дополнять вручную).
- `scripts/verify_gumar_runtime.py` теперь дополнительно проверяет: обязательные имена в `defer`, оба новых правила в промпте и что полный текст `SELF_IMPROVEMENT.md` (раздел «Ограничения») в промпт не протёк.

## 1.0.3 — 2026-10-06

- Always-on prompt сокращён до минимально необходимых правил: MASTER_SPEC core, PERMISSIONS, EXECUTION_POLICY, RESPONSE_POLICY и правила сохранения памяти. Смысл политик не менялся — сами policy-файлы не редактировались, bridge вставляет только их rule-секции.
- `ARCHITECTURE.md` больше не входит в system prompt; читается on-demand, когда задача касается архитектуры, Profile, specialist, subagent или делегирования.
- `ACTION_REGISTRY.md` больше не вставляется текстом: он подготовлен как программный registry — `policies/action_registry.json` (машинночитаемые записи: `id, type, description, when_to_use, input_schema, profile, permissions, risk, verification, version, status`) и загрузчик/валидатор `plugins/gumar-runtime-policy/registry.py`. Маршрутизатор выбирает зарегистрированный `action_id`; произвольные shell-команды запрещены.
- `MEMORY_POLICY.md` в prompt оставлен только правилами сохранения, обновления и секретов; уровни CORE/DOMAIN/EPISODIC и изоляция агентов — on-demand. В always-on впервые попала строка `Mode: B` (раньше она отфильтровывалась как метаданные).
- `QUALITY_POLICY.md`, `SELF_IMPROVEMENT.md`, `ACTIVE_TASKS_POLICY.md` остаются on-demand; `CHANGELOG.md` не загружается в prompt никогда.
- В bridge добавлен label-заголовок для каждой rule-секции: без него срезанный markdown превращал список правил в неоднозначный набор строк (терялись уровни риска и названия правил памяти).
- `scripts/verify_gumar_runtime.py` теперь проверяет минимальность always-on: обязательные маркеры правил, отсутствие полного текста политик в prompt, все on-demand ссылки, валидность registry, а также собственные бюджеты (≤3900 на секцию, ≤6300 суммарно против лимитов Hermes 4000/8000).
- Измеренный результат: always-on 3660 + 1695 = 5355 символов (framed 5607) против 3794 + 3881 = 7675 (framed 7933) — минус 29% постоянного prompt-расхода; системный промпт сессии 41 739 символов вместо 43 964.

## 1.0.2 — 2026-10-05

- Добавлены MEMORY_POLICY.md и RESPONSE_POLICY.md в runtime.
- MASTER_SPEC.md установлен как основной человекочитаемый источник конфигурации; в постоянный prompt входят только его приоритет инструкций и source-of-truth.
- HERMES_USER_PROFILE.md сохранён только как reference, чтобы не дублировать разнесённые политики.
- Always-on политики переразложены под лимиты native plugin system prompt; QUALITY_POLICY.md, SELF_IMPROVEMENT.md и ACTIVE_TASKS_POLICY.md подключены как on-demand policy references.

## 1.0.1 — 2026-10-05

- Конфигурационные файлы подключены к реальному Hermes runtime, а не только сохранены в репозитории.
- `SOUL.md` подключён через нативный identity loader Hermes.
- `USER.md` подключён через нативный `MemoryStore`; лимит user profile поднят минимум до 4000 символов.
- Остальные поведенческие политики подключены через `gumar-runtime-policy` и native plugin system-prompt sections.
- YAML-схемы и примеры остаются в source-of-truth файлах и не расходуют always-on prompt; перед структурными изменениями runtime требует прочитать полный policy-файл.
- Добавлена автоматическая проверка `scripts/verify_gumar_runtime.py`; `setup-hermes.sh` прекращает установку при неуспешной проверке.

## 1.0.0 — 2026-10-05

- Исходный `HERMES_USER_PROFILE.md` разделён на компактные runtime-политики.
- Добавлен человекочитаемый `MASTER_SPEC.md` как источник истины.
- Уточнены SOUL, USER и RESPONSE POLICY.
- Введены CORE, DOMAIN MEMORY, EPISODIC/ARCHIVE и Active Tasks.
- Добавлены типы записей памяти, provenance, confidence и обновление без дублей.
- Добавлены risk levels и правила подтверждений.
- Определены Profile-контракт, Specialist, Subagent и главный orchestrator.
- Подготовлены JEV routing, confidence fallback и eval dataset.
- Добавлены Action Registry, quality gate и self-improvement lifecycle.
