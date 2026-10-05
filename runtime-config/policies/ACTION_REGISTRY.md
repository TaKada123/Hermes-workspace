# ACTION REGISTRY

**Version:** 1.0.0  
**Updated:** 2026-10-05

Единый registry содержит только проверенные и разрешённые маршруты. JEV выбирает зарегистрированный `action_id`; произвольные shell-команды запрещены.

## Схема записи

```yaml
id: namespace.action_name
type: agent|script|workflow|tool|fallback
description: ...
when_to_use: ...
input_schema: ...
profile: main|engineering|coding|AI|visual|documents|home|finance
permissions: ...
risk: low|medium|high
verification: ...
version: 0.1.0
status: experimental|stable|deprecated|replaced
```

## Требования

- `id` уникален и стабилен.
- Inputs валидируются до выполнения.
- `profile` определяет допустимую память и инструменты.
- `permissions` не могут быть шире контракта Profile.
- Для `medium` и `high` применяются правила `PERMISSIONS.md`.
- `verification` обязателен для scripts и workflows, изменяющих состояние.
- `replaced` указывает новый `action_id` в описании или метаданных реализации.
- Registry не содержит секретов.

## Начальный fallback

```yaml
id: main.reasoning_fallback
type: fallback
description: Сложные, новые, междисциплинарные или неуверенно маршрутизируемые задачи.
when_to_use: Нет подходящего точного action_id или confidence маршрута низкий.
input_schema: Current request plus minimal permitted context.
profile: main
permissions: Inherit main profile and PERMISSIONS.md.
risk: low
verification: Compare result with original user goal and QUALITY_POLICY.md.
version: 1.0.0
status: stable
```
