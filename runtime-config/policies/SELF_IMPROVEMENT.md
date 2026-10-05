# SELF IMPROVEMENT

**Version:** 1.0.0  
**Updated:** 2026-10-05

## Цикл

```text
новая задача
→ reasoning
→ успешный проверенный результат
→ повторяемое решение: skill/workflow
→ детерминируемое решение: script/action
→ tests/verification
→ experimental
→ stable
→ Action Registry
→ доступность для JEV
```

## Ограничения

- Непроверенное решение не становится production action.
- Один успешный случай сам по себе не доказывает повторяемость.
- Не создавать почти одинаковый script, если существующий можно безопасно расширить.
- Перед повышением до `stable` определить inputs, errors, permissions, risk и verification.
- При замене старого действия пометить его `deprecated` или `replaced`, сохранив путь миграции.
- Изменения политик фиксировать в `CHANGELOG.md`.
