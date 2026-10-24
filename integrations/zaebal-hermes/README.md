# Z.A.E.B.A.L. → Hermes (локальный адаптер)

**Исходники готовы к проверке; live здесь не устанавливается.** Поддерживаются все существующие профили. Внешний аудитор строго выключен; история не отправляется другому агенту. Никаких model/provider/MCP изменений, сетевых или автоматических LLM-вызовов.

## Состав и поведение

- `plugin/__init__.py` регистрирует `pre_llm_call` и `/zaebal status`.
- `plugin/worker.py` запускает pinned upstream с `--host hermes` в ограниченном stdlib subprocess (2 секунды, без унаследованных секретов/PATH); аудит-хук запрещает дочерние процессы и сеть.
- `plugin/vendor/core/` — неизменённый upstream `16927bdbb03cf97dc81d914648cc192fe71201d3`; контрольные суммы в `plugin/vendor/SHA256.json`.
- В каждый runtime-вызов передаются только **текущий user_message и session_id**, не conversation_history/tool output. Историю читает сам уже работающий агент из своего контекста.
- Hook возвращает только динамический `{context: ...}`. Hermes добавляет его после исходного пользовательского текста через API sidecar; системный prompt, прежние сообщения и исходный user text не переписываются.
- Похвала/обычный текст/цитаты silent. Направленные жалобы: L1, L2, L2, L3 на 1–4 сигнале (точные правила upstream). Явное «продолжай» сбрасывает streak, не доказывая исправление. Ручной аудит — обычное сообщение **`zaebal audit` без `/`**, не увеличивает streak. `/zaebal audit` только подсказывает этот способ: slash handler не имеет достоверного session/turn id.
- По умолчанию auto/manual включены. Upstream-команды обычным сообщением `zaebal status`, `zaebal off`, `zaebal on`, `zaebal auto off/on` действуют только на текущую session; auditor при этом всегда принудительно none. `/zaebal status` показывает неизменяемую safety-policy и путь состояния, а не притворяется, что знает session slash-команды.
- Upstream просит двух внутренних аудиторов; отдельная host-policy запрещает любых дополнительных агентов/модели и передачу истории. Агент должен явно сообщить degraded/self-audit mode. Протоколы upstream не отредактированы. Это инструкция рабочей модели, а не глобальный запрет её tool calls; **сам адаптер** не вызывает никаких аудиторов.

### Изоляция и ограничения

Общий код находится в `<root>/plugins/zaebal-hermes`; named profiles получают symlink на него. Состояние **не в общем каталоге кода**:

```
<profile-home>/plugin-data/zaebal-hermes/turns.sqlite3
<profile-home>/plugin-data/zaebal-hermes/sessions/<sha256(session_id)>/
```

Идентификатор `(session_id, turn_id)` допускается только один раз, включая restart/reload. Состояние и настройки не разделяются с `~/.zaebal` или другими профилями/host. Перед runtime worker атомарно устанавливает `auditor=none`, `audit_levels=[]`, `auditor_command=''` под session lock; отравленный старый конфиг не включает аудитора. Нет raw prompt/history в dedup ledger.

При timeout/error — fail-open, без протокола; уже допущенный turn повторно не исполняется (at-most-once, не exactly-once). При crash после admission сигнал может потеряться; это намеренный выбор против двойной эскалации. Ledger не очищается автоматически: очистка может вернуть replay; удалять только вместе с заведомо завершёнными сессиями по отдельному решению. Поддерживаются текстовые user messages до 128000 символов; malformed/multimodal payload, пустые id и child session пропускаются. Upstream — эвристический детектор, не безошибочный анализ эмоций.

## Безопасная установка (выполняет родитель после review)

Только Linux; **не** запускать upstream `install.sh`. Не создаются новые профили; discovery включает default и существующие нескрытые каталоги `profiles/*` с `config.yaml`, исключая symlink-каталоги профилей. Не изменяются skills, memories, policies и model/provider settings. Перед enable сохраняется backup исходного config; unrelated настройки меняет/сохраняет официальный Hermes CLI, не наш YAML writer. Чужая/старая папка плагина вызывает preflight failure без перезаписи.

По умолчанию — read-only dry-run:

```bash
cd /home/vottak/Проекты/Hermes-workspace
python integrations/zaebal-hermes/install.py \
  --root /home/vottak/.hermes --all-profiles \
  --hermes /home/vottak/.local/bin/hermes
```

После просмотра точного списка targets:

```bash
python integrations/zaebal-hermes/install.py \
  --root /home/vottak/.hermes --all-profiles \
  --hermes /home/vottak/.local/bin/hermes --apply
```

Найденные в этой среде цели: `default`, `architect`, `coding`, `design`, `university`. При повторном запуске discovery выполняется заново. Изменённый upstream требует отдельной проверки; installer не обновляет/переписывает уже установленную отличающуюся версию. При частичном CLI failure остановиться и проверить выведенные targets/backup; multi-profile enable не является общей атомарной транзакцией, не обещает автоматический rollback всех профилей.

### Проверка после установки

Для каждого target home (default — `/home/vottak/.hermes`, остальные — `/home/vottak/.hermes/profiles/<name>`):

```bash
HERMES_HOME=/home/vottak/.hermes/profiles/design /home/vottak/.local/bin/hermes config get plugins.enabled --json
HERMES_HOME=/home/vottak/.hermes/profiles/design /home/vottak/.local/bin/hermes plugins list
```

В новом чате соответствующего профиля: `/zaebal status`; затем контролируемая направленная жалоба → L1. Canary создаёт реальный локальный streak, поэтому после него отправить «продолжай». Такой live-canary здесь **не выполнялся**.

### Граница активации — важна

В установленной версии `plugins enable` вызывает `activate_plugin_now`: может немедленно попросить gateway/Desktop backend перечитать плагины через control socket, **без restart процесса**. Если этот IPC сработает, hook применится к **следующему входящему user turn**, не к старой истории или текущему tool loop. Если не сработает — гарантирована загрузка в новом процессе Hermes; новый чат внутри старого процесса сам по себе не гарантирует rediscovery. Installer не перезапускает gateway/текущую сессию и не подменяет prompt. В рамках этой работы live `--apply` запрещён и не выполнен.

Отключение конкретного профиля — официальный CLI:

```bash
HERMES_HOME=/home/vottak/.hermes/profiles/design /home/vottak/.local/bin/hermes plugins disable zaebal-hermes
```

Оно тоже может hot-reload. Удалять общий source, пока на него ссылаются другие profiles, нельзя. Backups сохраняются в `<profile-home>/plugin-data/zaebal-hermes/install-backups/`; не восстанавливать их вслепую поверх новых concurrent config changes.

## Тесты

Канонический runner репозитория, отдельная ticket-suite, без всего Hermes monorepo:

```bash
cd /home/vottak/Проекты/Hermes-workspace
HERMES_PYTHON=/home/vottak/.hermes/installs/03497b76f3a1fc80/test-environment/gen-2927ba91537f45e0956e0e27bd7a1394/venv/bin/python \
  bash scripts/run_tests.sh integrations/zaebal-hermes/tests/ -q
```

`test_host.py` использует **реальный установленный** wrapper `/home/vottak/.local/bin/hermes`, CLI enable и PluginManager, но только с temporary HERMES_HOME под `/home/vottak/.hermes/cache/scratch`. Два home используют общий symlink source и одинаковые session/turn ids: оба независимо дают 1,2,2,3. Проверяются реальные `_collect_pre_llm_call_context` и `compose_user_api_content`, отсутствие изменения prefix/исходного текста, replay и tool output. Это host seam integration без модели, не доказательство поведения LLM после протокола.

## Provenance и governance

См. `plugin/PROVENANCE.md`: **в upstream нет LICENSE**. Приватная локальная копия не даёт разрешения на публикацию/распространение vendored runtime; сначала получить лицензию. Исходный dirty index/tracked файлы не входят в scope; commit не создаётся.

`install.py` — экспериментальный кандидат постоянного action. Родитель должен зарегистрировать его через обычный workflow action registry перед повторным использованием вне явно разрешённой текущей задачи. Здесь registry намеренно не меняется; текущая разработка/проверка выполняется через `main.reasoning_fallback`.
