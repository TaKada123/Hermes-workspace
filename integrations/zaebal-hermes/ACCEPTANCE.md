# Карта приёмки (до реализации)

Action: `main.reasoning_fallback`. Scope: только новый `integrations/zaebal-hermes`; live install, restart, commit и изменения registry запрещены. Актуальное уточнение пользователя: поддержка всех существующих профилей, общий source/runtime, строго profile-local state. Никаких новых профилей и изменений skills/memories/policies.

| Требование | Seam / инвариант | Доказательство |
|---|---|---|
| Реальный input boundary | установленный PluginManager → pre_llm_call(user_message, session_id, turn_id) | интеграционный тест свежего процесса без модели |
| Система prompt cache | только return {context}; входные аргументы неизменны | тест + call site agent/turn_context.py:804–858,1200 |
| Обычный текст, похвала, цитаты silent | публичный hook | параметризованный тест |
| Directed → L1/L2/L3 | неизменённый upstream runtime | 4 отдельных turn_id: 1,2,2,3 |
| Явное продолжай сбрасывает | публичный hook | L3 → level 0 → L1 |
| Нет replay / tool-output trigger | читается только user_message; нет fallback к истории | malformed/history/tool-loop тесты |
| Idempotency / concurrency | durable at-most-once claim session+turn, до запуска runtime | повторы, конкурентные вызовы, reload |
| Session/profile isolation | захваченный profile home; разные session_id | одинаковые session+turn в двух профилях; свежий installed loader в обоих |
| Auditor строго none | отдельный ZAEBAL_STATE_DIR, forced config; worker запрещает subprocess/network | L3 с отравленным config, sentinel и incidents |
| Pinned runtime | core, platform_runtime, wordlists, protocol, config с одного SHA | SHA256 manifest + сравнение upstream |
| Без live изменений | installer по умолчанию dry-run, --apply отдельно | isolated smoke + readback; исходный tracked diff/index неизменны |
| Безопасная активация | plugins enable через установленный CLI, без YAML-edit | README + dry-run; hot-reload через control socket возможен, свежий процесс гарантирован |

Upstream: https://github.com/howdeploy/Z.A.E.B.A.L.git @ 16927bdbb03cf97dc81d914648cc192fe71201d3.
LICENSE-файл в upstream отсутствует; не выдумывать лицензию. Зафиксировать ограничение в provenance; это приватная локальная интеграция, не разрешение на распространение.

Новый installer — кандидат experimental action; регистрация остаётся родительскому агенту. До этого запуск только в scope явно разрешённой текущей задачи через main.reasoning_fallback.
