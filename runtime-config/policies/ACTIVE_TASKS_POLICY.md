# ACTIVE TASKS POLICY

**Version:** 1.0.0  
**Updated:** 2026-10-05

Временные планы, идеи и текущие состояния не являются постоянной памятью. Они хранятся отдельно как Active Tasks.

## Статусы

`active | waiting | done | cancelled | stale`

## Минимальная запись

```yaml
id: task_id
title: ...
status: active|waiting|done|cancelled|stale
created_at: ISO-8601
updated_at: ISO-8601
next_action: ...
source: ...
```

## Правила

- Hermes может позже спросить: «У вас была такая задача. Она ещё актуальна?»
- После ответа обновить статус.
- Закрывать выполненное как `done`, отказ как `cancelled`, неподтверждённое устаревшее как `stale`.
- Удалять запись только по подтверждению или согласно отдельно утверждённой retention-политике.
- Не переносить временный `state` в постоянный USER profile без долгосрочной ценности.
