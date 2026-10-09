# Hermes Agent

Глоссарий проекта Hermes-workspace (форк Hermes Agent с runtime-конфигурацией и интеграцией Architecture 2.0). Термины ниже — каноническая лексика области долговременной памяти; используй их в спецификациях, тикетах и тестах.

## Memory architecture

**Canonical store**
Единственный источник истины долговременной памяти профиля: отдельная SQLite-база (memory.db) в каждом HERMES_HOME с типизированными записями (fact, decision, constraint, preference, pattern, legacy), статусами, важностью, уверенностью и провенансом.
_Avoid_: memory file, файл памяти

**Memory projection**
Человекочитаемая, git-trackable проекция активных записей (MEMORY.md, USER.md), пересоздаваемая из canonical store после каждой мутации. Производные данные: ручные правки файла перезаписываются при следующей записи.
_Avoid_: память, source of truth

**Legacy store**
Текущая flat-file реализация MemoryStore (MEMORY.md/USER.md как источник истины).
_Avoid_: старый формат

**Memory consumer**
Любой компонент, читающий или пишущий память через bus: main agent, субагент (только через briefing), cron, background review.
_Avoid_: клиент памяти

**Capability**
Именованное право потребителя: read:memory, read:user, write:memory, write:user, rollback:memory, rollback:user. Rollback — отдельное право, не подразумеваемое write-ом.
_Avoid_: право доступа, permission

**Consumer spec**
Декларативные потребности одного потребителя: набор capabilities + опциональный project realm. Валидируется при подписке; read-only spec структурно не может писать и откатывать.
_Avoid_: профиль потребителя

**Project realm**
Опциональная проектная область потребителя: retrieval видит только записи своего проекта и глобальные.
_Avoid_: scope проекта

**Context pack**
Ограниченная token budget-ом подборка релевантных записей, вставляемая только в API-копию текущего сообщения пользователя — никогда в system prompt или сохранённую историю.
_Avoid_: сниппет памяти, фрагмент контекста

**Memory briefing**
Одноразовая неизменяемая read-only копия релевантных записей, которую родитель добавляет в goal субагента. Субагент не получает memory tool, bus handle и доступ к БД.
_Avoid_: доступ к памяти субагента

**Supersede / deprecate**
Семантика пересмотра standing-записей: новая запись помечает старую как deprecated и пишет связь провенанса. Решения и ограничения не перезаписываются молча.
_Avoid_: удалить, перезаписать (для decision/constraint)

**Downgrade export**
Проверяемый экспорт записей, созданных после cutover, обратно в legacy-файлы перед выключением sqlite_v2; memory.db при этом сохраняется.
_Avoid_: откат

**Migration manifest**
Отчёт одноразовой миграции: хеши исходных файлов, распознано/импортировано записей, пропущенные с причиной, маркер идемпотентности.
_Avoid_: лог миграции

**Cutover**
Момент переключения backend flag профиля с legacy на sqlite_v2 (и обратно).
_Avoid_: включение

**Backend flag**
Профильная настройка выбора backend (legacy file store | sqlite_v2). Во время rollout значение по умолчанию — legacy.
_Avoid_: feature switch
