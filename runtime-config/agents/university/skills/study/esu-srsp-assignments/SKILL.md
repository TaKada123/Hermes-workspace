---
name: esu-srsp-assignments
description: "Use when writing or submitting ESU СРСП assignments."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [study, esu, srsp, telegram, docx, university]
    category: study
    related_skills: [docx, xlsx]
---

# ESU СРСП Assignments

How coursework (СРСП) is written, formatted and handed in at the user's university. Load this
before drafting, calculating or formatting a СРСП answer, or before touching the task topics in
the university Telegram forums.

## When to Use

- The user asks to write, calculate, format or check a СРСП (or any graded coursework) for
  Макроэкономика / Менеджмент.
- A new task or deadline appears in one of the university Telegram groups.
- The user asks what format, header or hand-in channel the university requires.
- Anything is about to be written into those groups or sent to `@esu_study_bot`.

## Where the work lives

The university runs two forum-style Telegram groups, one per discipline:

- `Макроэкономика_ESU` — chat id `-1003945205219`
- `Менеджмент_ESU` — chat id `-1004453618363`

Each is split into topics ("подчаты"): `General`, `📢 Объявления`, `📚 Материалы занятий`,
`📝 Задания и дедлайны`, `❓ Вопросы`. **Tasks are posted in `📝 Задания и дедлайны`** by the
course bot `ESU_Учебный помощник` (`@esu_study_bot`); assignment messages start with `📝`.
Deadlines and date corrections appear in that same topic.

Read them through the `tguser` monitor (read-only user-account adapter): it copies every message
from the three watched chats into `~/.hermes/tguser/inbox.jsonl` and downloads attachments into
`~/.hermes/tguser/media/`. The monitor never posts into a group — do not promise a student-visible
reply there. Anything the agent must show the user goes to the account's Saved Messages
("Избранное") or through the `telegram` bot DM.

## The five things that make a СРСП acceptable

1. **Header, always.** Discipline · topic number and name · full name (фамилия, имя, отчество)
   · academic group · submission date. The work is found in the grade sheet by this header, so a
   missing field means the work is not counted. The file students submit is
   `assets/Шаблон_СРСП.docx`.
2. **Length: about half a page, 1 500–2 000 characters.** Coherent prose, not a list of bullet
   theses. If the task needs an example or a calculation, put it inside the text.
3. **Typography:** Times New Roman 14, line spacing 1,5, first-line indent 1,25 cm, justified;
   margins left 3 cm, right 1 cm, top and bottom 2 cm.
4. **Sources section only if sources were used** — author, title, year; for a website add the date
   accessed. No sources used → delete the section instead of writing "нет".
5. **Hand-in destination: the bot `@esu_study_bot` in a private chat, never the group.** The bot
   asks (by button) which assignment it is and confirms receipt.

## Two submission formats

- Electronically, using `assets/Шаблон_СРСП.docx` — send `.docx` or `.pdf`.
- By hand — write legibly on paper, then send a photo or scan. The photo must be readable: even
  light, the whole sheet, no blur. An unreadable photo is returned for rework **and the deadline
  keeps running**.

## Procedure

1. Read the newest `📝` message in `📝 Задания и дедлайны` for that discipline — that is the task,
   not the surrounding student chatter in the same topic.
2. Pull the deadline from the same topic; the bot restates it whenever it moves.
3. Do the actual work: calculations and examples go inside the text, no placeholders.
4. Produce the answer in the submission format (use the `docx` skill when it must look like the
   template) with every header field filled in.
5. Show it to the user in Избранное or through the bot; the student hands it in. Never send into
   the groups.

## Pitfalls

- **Answering in the group.** Topics mix tasks with student chatter: only the bot's `📝` message
  is the task, the rest is classmates talking.
- **A list of theses instead of prose.** Fails the "связный текст" rule even when the content is right.
- **Forgetting the header.** A correct answer is not counted without it.
- **An empty "Источники" section** instead of deleting it.
- **Handing in through the group** — the bot only accepts private messages.
- **Assuming the deadline from the task date** — check the deadline line, it is frequently moved.
