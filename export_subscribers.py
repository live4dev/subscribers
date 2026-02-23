"""
Разовый экспорт текущих подписчиков канала через Telethon (MTProto API).

Нужно один раз:
  1. Добавить API_ID и API_HASH в .env (получить на https://my.telegram.org)
  2. Запустить скрипт и пройти авторизацию по номеру телефона

После первого запуска сессия сохраняется в subscriber_export.session —
повторная авторизация не потребуется.

Запуск:
  python export_subscribers.py
  python export_subscribers.py @mychannel          # без интерактивного ввода
  python export_subscribers.py -1001234567890      # по Bot API ID

Данные записываются в data/{channel_id}.txt в том же формате, что использует бот.
Существующие записи не перезаписываются — сохраняется исходная дата first_seen.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_ID_RAW = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")

if not API_ID_RAW or not API_HASH:
    print("Ошибка: API_ID и API_HASH не заданы в .env")
    print("Получить можно на https://my.telegram.org → API development tools")
    sys.exit(1)

try:
    API_ID = int(API_ID_RAW)
except ValueError:
    print("Ошибка: API_ID должен быть числом")
    sys.exit(1)

try:
    from telethon import TelegramClient
    from telethon.errors import ChatAdminRequiredError, ChannelPrivateError
except ImportError:
    print("Ошибка: установите telethon:")
    print("  pip install telethon")
    sys.exit(1)

import storage

DATA_DIR = Path("data")


def _bot_api_id(telethon_id: int) -> int:
    """Конвертировать Telethon channel ID → Bot API ID (-100XXXXXXXXX)."""
    return int(f"-100{telethon_id}")


def _telethon_id(bot_api_id: int) -> int:
    """Конвертировать Bot API ID (-100XXXXXXXXX) → Telethon channel ID."""
    return abs(bot_api_id) - 1000000000000


def _parse_channel_arg(raw: str):
    """Разобрать аргумент: вернуть username-строку или числовой Telethon ID."""
    raw = raw.strip()
    if raw.lstrip("-").isdigit():
        n = int(raw)
        # Bot API format: отрицательное число, abs начинается с 100
        if n < 0 and str(abs(n)).startswith("100"):
            return _telethon_id(n)
        return n
    return raw  # @username или t.me/...


async def export_channel(client: TelegramClient, channel_arg) -> None:
    # Получаем entity канала
    try:
        entity = await client.get_entity(channel_arg)
    except ValueError:
        print(f"Канал не найден: {channel_arg!r}")
        print("Убедитесь, что вы подписаны на канал или являетесь его администратором.")
        return
    except ChannelPrivateError:
        print("Канал приватный и недоступен для вашего аккаунта.")
        return

    channel_id = _bot_api_id(entity.id)
    title = getattr(entity, "title", str(channel_arg))
    print(f"\nКанал: {title}")
    print(f"Bot API ID: {channel_id}")
    print("Загружаю список участников...\n")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = 0
    added = 0
    skipped = 0

    try:
        async for participant in client.iter_participants(entity):
            if getattr(participant, "bot", False):
                continue

            is_new, _ = storage.add_subscriber(channel_id, participant.id)
            total += 1
            if is_new:
                added += 1
            else:
                skipped += 1

            if total % 200 == 0:
                print(f"  Обработано: {total} (новых: {added}, уже в базе: {skipped})...")

    except ChatAdminRequiredError:
        print("Ошибка: для экспорта нужны права администратора канала.")
        return
    except Exception as e:
        print(f"Ошибка при получении участников: {e}")
        return

    print(f"\nГотово!")
    print(f"  Всего участников обработано : {total}")
    print(f"  Добавлено в базу            : {added}")
    print(f"  Уже были в базе             : {skipped}")
    print(f"  Файл                        : data/{channel_id}.txt")


async def main() -> None:
    print("=== Экспорт подписчиков канала (Telethon) ===\n")

    # Канал можно передать аргументом командной строки
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = input("Введите @username или ID канала: ").strip()

    if not raw:
        print("Канал не указан.")
        return

    channel_arg = _parse_channel_arg(raw)

    print("\nАвторизация в Telegram...")
    print("При первом запуске потребуется ввести номер телефона и код из приложения.\n")

    async with TelegramClient("subscriber_export", API_ID, API_HASH) as client:
        await export_channel(client, channel_arg)


if __name__ == "__main__":
    asyncio.run(main())
