#!/usr/bin/env python3
"""QR-code login helper for the ``tguser`` platform plugin (no login code needed).

Telegram's login *code* flow is easy to get wrong (the code is short-lived, it arrives
in the Telegram app on another device, and a couple of wrong attempts trigger a
FloodWait). The QR flow avoids codes entirely: this script draws a QR in the terminal,
you scan it from the phone you are already signed in on
(Telegram -> Settings -> Devices -> Link Desktop Device), and the session is created.

Run it with the SAME interpreter the gateway uses:

    /home/vottak/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3 \
        /home/vottak/.hermes/plugins/tguser/login_qr.py

It reads TELETHON_API_ID / TELETHON_API_HASH / TGUSER_SESSION from <HERMES_HOME>/.env the
same way login.py does (falling back to the process environment), and writes the session
to the resolved TGUSER_SESSION path. It never prints the api_hash or the session contents.
A two-factor password, if the account has one, is asked for in YOUR terminal via getpass.
"""

import asyncio
import os
import sys
import time


def _hermes_home() -> str:
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        return os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return str(get_hermes_home())


def _load_profile_env() -> None:
    """Populate ``os.environ`` from the profile ``.env`` without overriding existing values."""
    home = _hermes_home()
    env_path = os.path.join(home, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def _draw_qr(url: str, terminal_width: int = 0) -> None:
    """Render *url* as an ASCII QR code (falls back to the raw link when qrcode is absent)."""
    try:
        import qrcode
    except ImportError:
        print("  (модуль qrcode не установлен — откройте ссылку вручную)")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True, tty=terminal_width > 0)


async def _run() -> int:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.errors.rpcerrorlist import FloodWaitError

    api_id = (os.environ.get("TELETHON_API_ID") or "").strip()
    api_hash = (os.environ.get("TELETHON_API_HASH") or "").strip()
    home = _hermes_home()
    session = os.path.expanduser(
        (os.environ.get("TGUSER_SESSION") or os.path.join(home, "tguser", "tguser")).strip()
    )
    if not api_id or not api_hash:
        print("ОШИБКА: TELETHON_API_ID и TELETHON_API_HASH должны лежать в <HERMES_HOME>/.env "
              "(файл /home/vottak/.hermes/.env).")
        return 2

    os.makedirs(os.path.dirname(session) or ".", mode=0o700, exist_ok=True)
    client = TelegramClient(session, int(api_id), api_hash)
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"Уже авторизовано: {getattr(me, 'first_name', '')} (id={getattr(me, 'id', None)})")
            print(f"Сессия: {session}.session")
            return 0

        print("")
        print("=== Вход по QR (код не нужен) ===")
        print("1. Откройте Telegram на телефоне, где вы уже вошли в аккаунт.")
        print("2. Настройки -> Устройства (Devices) -> Подключить устройство.")
        print("3. Наведите камеру на QR ниже. Если окно терминала узкое — растяните его")
        print("   и запустите команду заново: QR должен быть квадратным.")
        print("")
        deadline = time.time() + 240
        while time.time() < deadline:
            qr = await client.qr_login()
            print(f"--- QR (действует ~40 секунд) ---")
            _draw_qr(qr.url)
            print("Если сканер не срабатывает, вот ссылка для ручного ввода (не отправляйте её никому):")
            print(qr.url)
            print("")
            try:
                await qr.wait(timeout=45)
                break
            except asyncio.TimeoutError:
                print("QR истёк, показываю новый...\n")
                continue
            except SessionPasswordNeededError:
                import getpass
                password = getpass.getpass("Двухфакторный пароль (ввод не отображается): ")
                await client.sign_in(password=password)
                break
            except FloodWaitError as exc:
                wait = int(getattr(exc, "seconds", 0)) or 60
                print(f"Telegram просит подождать {wait} с (слишком много попыток входа). Жду...")
                await asyncio.sleep(wait + 2)
                continue
            except Exception as exc:  # noqa: BLE001 - type only, never the payload
                print(f"Ошибка входа: {type(exc).__name__}. Показываю новый QR...\n")
                continue

        if not await client.is_user_authorized():
            print("")
            print("Не удалось авторизоваться за отведённое время. Запустите скрипт заново.")
            return 1

        me = await client.get_me()
        name = " ".join(p for p in (getattr(me, "first_name", None), getattr(me, "last_name", None)) if p) \
            or getattr(me, "username", None) or "unknown"
        print("")
        print(f"ГОТОВО: вошли как {name} (id={getattr(me, 'id', None)})")
        print(f"Файл сессии: {session}.session")
        print("")
        print(f"Ваш TGUSER_ALLOWED_USERS={getattr(me, 'id', None)} — именно этот id сможет давать")
        print("агенту задания; все остальные сообщения из канала пойдут только в лог.")
        print(f"Вход виден в Telegram -> Настройки -> Устройства; отозвать можно там же.")
        return 0
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def main() -> int:
    os.umask(0o077)  # newly created sessions and private outputs are owner-only
    _load_profile_env()
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
