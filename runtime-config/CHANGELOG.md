# Changelog

Все существенные изменения конфигурации Hermes фиксируются здесь.

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
