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

## Direct Blender work in Main

```yaml
id: blender.direct
type: workflow
description: Прямая работа Main в Blender через MCP по явной просьбе пользователя, без design.route.
when_to_use: Пользователь явно просит выполнять Blender-задачу непосредственно в Main; остальные визуальные запросы остаются в design.route.
input_schema: User request; explicit project and references; requested animation timing and verification frames.
profile: main
permissions: Inherit PERMISSIONS.md; verify workspace and port; checkpoint before edits; one scene writer; no arbitrary deletion, paid services or source overwrite.
risk: medium
verification: get_scene_info before edits; static composition checked with look camera/angles before keyframes; look frames 1,24,48,72,96 and final; saved blend and preview verified.
version: 1.0.0
status: experimental
skills: blender-mcp, cinedance, acting-system, lira-image-prompts; required references loaded
```

## Ecommerce card design
```yaml
id: ecommerce_card.create
type: agent
description: Создать и проверить карточку товара или комплект изображений для маркетплейса через subordinate-агента Design Agent.
when_to_use: Карточка товара, листинг, маркетплейс, Amazon A+, инфографика товара, size chart, lifestyle, banner или комплект ecommerce-изображений.
input_schema: Original request; platform/market/language; explicit product references; verified product facts and exact copy; output path; explicit USER approval and stated maximum budget for any paid generation or external upload.
profile: design
permissions: Design profile contract; project-scoped files; paid generation or external upload only after explicit USER approval and a stated maximum budget; otherwise NEEDS_APPROVAL.
risk: medium
verification: Every output file exists and is visually checked for product identity, exact text, platform dimensions/rules and unsupported claims; Design Agent performs the final quality gate.
version: 1.0.0
status: stable
parent_agent: design
subagent_instruction: agents/ecommerce-card-designer.md
domain_skill: ecommerce-listing-suite
lifecycle: temporary-subagent
may_delegate: false
approval_gate: paid_generation|external_upload require approver=USER and budget_required=true; missing_status=NEEDS_APPROVAL
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

## GitHub CI verification

```yaml
id: github.ci_verify
type: workflow
description: Для кодовой задачи выполнить быстрые проверки локально и проверить долгие тесты в GitHub Actions ближе к завершению тикета.
when_to_use: Работа в GitHub-репозитории, особенно implementation ticket перед закрытием или PR review.
input_schema: Repository and remote ref; ticket/PR; available workflow; latest intended commit SHA; quick local check results.
profile: coding
permissions: Read repository/CI state; workflow dispatch only when authorized by the request and repo policy; no push without explicit authorization.
risk: medium
verification: GitHub Actions run is terminal; repository, workflow, branch/ref and head SHA match intended ticket commit; conclusion and artifacts/status checks read back from GitHub.
version: 1.0.0
status: stable
```
