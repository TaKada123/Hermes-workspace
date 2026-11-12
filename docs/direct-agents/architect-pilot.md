# Architect: прямой самостоятельный агент — пилот

## Утверждённый scope

Пользователь оставляет Main, Design, Coding, University, Architect и временных подагентов; обращается к ним напрямую. Версионируемые определения остаются в Hermes-workspace. Рабочие homes располагаются в /home/vottak/Проекты/Hermes; проекты отдельно. Этот пилот касается только Architect. Старый профиль /home/vottak/.hermes/profiles/architect остаётся нетронутым для отката. Другие profiles, Gateway, AG2 и secrets не изменяются. Не выполнять push.

## Пилотный результат

- Определение роли, безопасный manifest, необходимые skills/scripts/references в runtime-config/agents/architect.
- Рабочий home /home/vottak/Проекты/Hermes-workspace/agents/architect; отдельные память/история, сохранённые из source, не общие symlinks на memory/session DB.
- Прямой launcher с явным HERMES_HOME, без -p architect (иначе выбирается старый профиль). Доступен в рабочей папке и через отдельную команду architect-direct; старые launcher не заменять.
- Сохраняются текущие model gpt-6-sol-900k, memory backend/limits, tool defer, Code Graph и Context7, заебал-плагин. У нового home отключены agent-network и Main policy router; общие safety и роль описаны в собственном SOUL. Без модели и без трат на этапе подготовки.
- Skills/scripts/refs сохраняются без скрытого удаления; существующие зависимости MCP могут оставаться внешними с явными путями. Реальные MCP вызовы проверяет родитель.
- Не мигрировать файловую memory в sqlite_v2 в этом пилоте; FTS5 истории сохранить. Отдельная миграция памяти — отдельное решение.
- Приватные USER/MEMORY/session DB/credentials никогда не попадают в репозиторий. Secrets не выводятся и не копируются в source. Способ доступа к общему OAuth сверить с runtime; не дублировать refresh token.
- Первый install только в отсутствующий/пустой target. Повторный install не сбрасывает state, модель или плагины; отказ безопаснее молчаливой перезаписи.

## Приёмка и evidence map

1. Публичный installer CLI: установка на временной фикстуре сохраняет содержимое memory/history; SQLite backup API, не raw copy активной DB/WAL. Тест отказывает при занятом target/опасном пересечении путей. Новый home закрыт для других пользователей.
2. Публичный launcher: --help/config path выбирает target, аргументы передаются argv без eval, cwd проекта пользователя не подменяется незаметно; из папки агента default рабочий каталог отдельно от репозитория definitions.
3. Git/source: только allowlisted публичные definitions, role и инструменты; scanner/проверка индекса исключает secret/state/cache/private memory. Fixtures синтетические, не содержат пользовательские записи.
4. Реальная установка: сравнение приватных файлов hash/DB row counts без печати содержимого; source остаётся неизменённым. Offline fresh prompt содержит Architect role и не содержит Main routing/agent-network. Установленные skills и два MCP проверены отдельно.
5. CLI model smoke при необходимости — ограниченный read-only запуск существующей подписки, только новый home, не Gateway; фиксировать реальный session/result. Не считать offline prompt равным model E2E.
6. Scope/rollback: никаких service restart, отключения старого профиля или удаления state. Откат — использовать старый профиль; новое рабочее дерево оставляется до явного решения.

## Verification discipline

Применяются implement/fast-delivery и code-review. Tests через scripts/run_tests.sh с существующим test interpreter; без установки пакетов в live venv. Независимое ревью перед local commit. Для пилота не запускать огромный unrelated monorepo suite и не называть focused pass полным CI. На момент начала repo чист, branch mem-v2-integration, checkpoint e6dca00e. Архивные теги уже опубликованы.
