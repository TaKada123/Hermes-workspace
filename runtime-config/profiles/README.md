# Profile snapshots

This directory contains sanitized snapshots of selected configured Hermes profiles. It is not a full Hermes installation and does not include profile secrets, auth state, sessions, private memory databases, transcripts, browser state or caches.

Each profile's `SOUL.md` captures its role/instructions at export. `config.example.json` contains only a safe subset of non-secret settings; it is an example, not an overwrite-ready replacement for an existing profile's complete `config.yaml`. `skills-inventory.json` is a names/categories index; standard Hermes skills are supplied by Hermes and are not vendored here.

The design profile also has a native installer and verifier (`scripts/install_design_profile.py`, `scripts/verify_design_profile.py`). The architect, coding and university folders are snapshots only; there is no installer for those snapshots yet. For university, the local template asset is included where permitted, and `plugins/tguser/` contains adapter source only. To restore monitoring on another machine, configure fresh credentials in that profile's private `.env`, establish a new Telegram session locally, and install Telethon into the live Hermes-managed profile environment. Never commit `.env`, Telegram `.session` files, chat transcripts, inboxes or downloaded private media.

Important: the current bundle does not implement autonomous collaboration between university and design profiles. `runtime-config/DOMAIN_MAP.md` records that limitation and the intended requirement to announce cross-domain participation before work. Do not describe the design goal as a working feature until its classifier, attributed shared task context, automatic handoff/continuation, dual review and escalation rules exist and pass tests.
