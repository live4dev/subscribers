"""
Хранилище подписчиков в текстовых файлах.

Формат файла data/{channel_id}.txt:
    # user_id|first_seen|status
    123456789|2024-01-15 10:30:00|active
    987654321|2024-01-16 11:00:00|inactive

Статусы:
    active   — сейчас подписан
    inactive — когда-то был подписан, но ушёл
"""

from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")


def _get_file(channel_id: int) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    return DATA_DIR / f"{channel_id}.txt"


def _load(channel_id: int) -> dict[int, dict]:
    """Загрузить подписчиков из файла.
    Возвращает: {user_id: {'first_seen': str, 'status': str}}
    """
    file = _get_file(channel_id)
    result: dict[int, dict] = {}

    if not file.exists():
        return result

    with open(file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != 3:
                continue
            try:
                user_id = int(parts[0])
            except ValueError:
                continue
            result[user_id] = {"first_seen": parts[1], "status": parts[2]}

    return result


def _save(channel_id: int, subscribers: dict[int, dict]) -> None:
    """Сохранить подписчиков в файл."""
    file = _get_file(channel_id)
    with open(file, "w", encoding="utf-8") as f:
        f.write("# user_id|first_seen|status\n")
        for user_id, data in subscribers.items():
            f.write(f"{user_id}|{data['first_seen']}|{data['status']}\n")


def add_subscriber(channel_id: int, user_id: int) -> tuple[bool, str]:
    """Зафиксировать подписку.

    Возвращает (is_new, first_seen):
        is_new=True  — этот пользователь никогда раньше не был подписан
        is_new=False — возвращение после отписки
        first_seen   — дата первой подписки
    """
    subscribers = _load(channel_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id not in subscribers:
        subscribers[user_id] = {"first_seen": now, "status": "active"}
        _save(channel_id, subscribers)
        return True, now

    first_seen = subscribers[user_id]["first_seen"]
    subscribers[user_id]["status"] = "active"
    _save(channel_id, subscribers)
    return False, first_seen


def remove_subscriber(channel_id: int, user_id: int) -> str | None:
    """Зафиксировать отписку.

    Возвращает first_seen (дату первой подписки) или None, если пользователь
    не был в базе.
    """
    subscribers = _load(channel_id)

    if user_id not in subscribers:
        return None

    first_seen = subscribers[user_id]["first_seen"]
    subscribers[user_id]["status"] = "inactive"
    _save(channel_id, subscribers)
    return first_seen


def get_stats(channel_id: int) -> dict:
    """Статистика по каналу."""
    subscribers = _load(channel_id)
    active = sum(1 for s in subscribers.values() if s["status"] == "active")
    total = len(subscribers)
    return {"active": active, "total": total, "inactive": total - active}
