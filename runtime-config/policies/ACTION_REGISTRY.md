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

## Design routing

```yaml
id: design.route
type: agent
description: Передать визуальную задачу из Main/JEV в изолированный профиль Design Agent.
when_to_use: Дизайн, сайт, презентация, портфолио, визуальная система, графика, layout, branding или visual editing.
input_schema: Original user request verbatim; explicit attachments; minimal routing metadata and project context.
profile: design
permissions: Inherit design profile contract and PERMISSIONS.md; no Main memory inheritance.
risk: low
verification: Result comes from profile design; original request hash is preserved; no unrelated Main context is included.
version: 1.0.0
status: stable
route_type: profile
route_id: design
```

## Engineering portfolio workflows

```yaml
id: engineering_portfolio.create
type: workflow
description: Создать новое портфолио инженерных сетей.
when_to_use: Нет утверждённого baseline/design system или пользователь явно просит новую концепцию.
input_schema: Design brief, audience, verified facts, permissions, assets, format and languages.
profile: design
permissions: Design profile contract plus project-scoped files and approved external generation.
risk: medium
verification: Real artifact render, facts, assets, language and links are checked; paid generation requires prior approval.
version: 1.0.0
status: stable
---
id: engineering_portfolio.extend
type: workflow
description: Расширить существующее инженерное портфолио без редизайна.
when_to_use: Утверждённые baseline и design system существуют; добавляется новый контент.
input_schema: Existing design system, approved baseline, new verified content and explicit project context.
profile: design
permissions: Design profile contract and project-scoped edits.
risk: medium
verification: New content follows the existing system; affected render is checked; Superdesign is not called by default.
version: 1.0.0
status: stable
---
id: engineering_portfolio.edit
type: workflow
description: Выполнить минимальную локальную правку инженерного портфолио.
when_to_use: Точное изменение текста, числа, ссылки, изображения или локального стиля.
input_schema: Existing artifact target and exact requested replacement.
profile: design
permissions: Design profile contract and minimal project-scoped edit.
risk: medium
verification: Requested literal or asset changed only in intended locations; local render checked; no redesign tools called.
version: 1.0.0
status: stable
```
