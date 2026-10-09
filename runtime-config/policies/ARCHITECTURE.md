# ARCHITECTURE

**Version:** 1.0.0  
**Updated:** 2026-10-05

## Начальные домены

`main | design | engineering | coding | AI | visual/video | documents | home | finance`

Домен не обязан быть отдельным агентом. Он может остаться skill, workflow или capability, если ему не нужны собственные memory, model, tools или permissions.

## PROFILE / SPECIALIST AGENT

Постоянная роль с отдельным контрактом:

```yaml
role: ...
allowed_memory: [...]
forbidden_memory: [...]
model: ...
skills: [...]
tools: [...]
MCP: [...]
actions: [...]
permissions: ...
escalation_target: main
```

Новый постоянный Profile создаётся только при реальной необходимости в отдельных memory, model, skills, tools, MCP или permissions.

## DESIGN AGENT

`design` — нативный Hermes Profile и ведущий специалист визуального домена. Он имеет собственные SOUL, config, sessions, skills и profile memory; не получает автоматически память или историю `main` и других доменов.

Внутренняя иерархия:

```text
Design Agent
  → domain skill
      → Superdesign только для исследования концепций
      → Impeccable только для critique/audit/polish
      → browser/computer-use/vision для проверки рендера
      → image/PDF/SVG/HTML/presentation tools для исполнения
```

`engineering-portfolio` — domain skill профиля `design`, а не отдельный постоянный агент. Его зарегистрированные режимы: `engineering_portfolio.create`, `engineering_portfolio.extend`, `engineering_portfolio.edit`.

## Временный routing до JEV

Main Hermes маршрутизирует визуальные запросы через `design.route` и передаёт профилю `design` исходный user request verbatim, явные attachments и минимальный project context. Main не загружает Superdesign, Impeccable или engineering-portfolio и не передаёт свой reasoning или нерелевантную память.

После подключения JEV меняется только верхняя точка выбора маршрута: `JEV → design.route → profile design`. Внутренняя архитектура Design Agent не меняется.

## SUBAGENT

Временный исполнитель конкретной подзадачи. Получает ограниченный контекст, выполняет работу и возвращает результат родителю. Не получает автоматически долговременную память и доступ других доменов.

## Главный Hermes

- orchestrator, fallback и контролёр качества;
- не обязан выполнять всё сам;
- делегирует с критериями приёмки;
- проверяет ответ относительно исходной цели;
- `completed` не означает «хорошо»;
- слабый результат отправляет на переработку тому же или другому исполнителю;
- отвечает за финальный результат.

## Будущий JEV

```text
USER
  → JEV ROUTER
      → DIRECT ACTION
      → SPECIALIST
      → MAIN
      → CLARIFY
```

JEV выбирает только зарегистрированный `action_id` и не генерирует произвольные shell-команды.

### Confidence / fallback

- высокая уверенность → `DIRECT`;
- средняя → `SPECIALIST`;
- низкая → `MAIN`;
- недостаточно входных данных → `CLARIFY`.

Числовые thresholds определяются позже по eval dataset.

### Eval dataset

```yaml
query: ...
expected_route: ...
actual_route: ...
confidence: 0.0-1.0
result: success|failure
notes: ...
```

Главный Hermes остаётся fallback для сложных, новых, междисциплинарных и неуверенно маршрутизируемых задач.
