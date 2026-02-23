"""
Telegram-бот для отслеживания подписчиков каналов.

Требования к боту:
  - Бот должен быть администратором канала
  - Нужны права: «Управление каналом» (manage_chat)

Запуск:
  python bot.py

Команды (отправлять боту в личку или в чат):
  /stats — статистика по всем известным каналам
"""

import logging
from pathlib import Path

from telegram import ChatMember, Update
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

import storage
from config import BOT_TOKEN, NOTIFICATION_CHAT_ID

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _user_label(user) -> str:
    """Человекочитаемое имя пользователя."""
    if user.username:
        return f"@{user.username}"
    name = user.first_name or ""
    if user.last_name:
        name = f"{name} {user.last_name}".strip()
    return f"{name} (ID: {user.id})" if name else f"ID: {user.id}"


def _channel_label(chat) -> str:
    """Человекочитаемое имя канала."""
    if chat.username:
        return f"@{chat.username}"
    return f"{chat.title} (ID: {chat.id})"


def _is_subscriber(status: str) -> bool:
    """Считать ли статус «подписчик»."""
    return status in (
        ChatMember.MEMBER,
        ChatMember.ADMINISTRATOR,
        ChatMember.OWNER,
    )


# ---------------------------------------------------------------------------
# Обработчики
# ---------------------------------------------------------------------------

async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Реагирует на изменение состава канала."""
    event = update.chat_member
    if event is None:
        return

    chat = event.chat
    old = event.old_chat_member
    new = event.new_chat_member
    user = new.user

    was_sub = _is_subscriber(old.status)
    now_sub = _is_subscriber(new.status)

    if was_sub == now_sub:
        # Сменился ранг внутри канала (например, стал/перестал быть админом),
        # но факт подписки не изменился — игнорируем.
        return

    channel = _channel_label(chat)
    person = _user_label(user)

    if not was_sub and now_sub:
        # Подписался
        is_new, first_seen = storage.add_subscriber(chat.id, user.id)
        if is_new:
            text = (
                f"✅ Новый подписчик!\n"
                f"Канал: {channel}\n"
                f"Пользователь: {person}\n"
                f"Первая подписка: {first_seen}"
            )
        else:
            text = (
                f"↩️ Вернулся подписчик!\n"
                f"Канал: {channel}\n"
                f"Пользователь: {person}\n"
                f"Впервые замечен: {first_seen}"
            )
        logger.info("Joined  channel=%s user=%s new=%s", chat.id, user.id, is_new)

    else:
        # Отписался / кикнут
        first_seen = storage.remove_subscriber(chat.id, user.id)
        text = (
            f"❌ Отписался!\n"
            f"Канал: {channel}\n"
            f"Пользователь: {person}"
        )
        if first_seen:
            text += f"\nВпервые подписался: {first_seen}"
        logger.info("Left    channel=%s user=%s", chat.id, user.id)

    await context.bot.send_message(chat_id=NOTIFICATION_CHAT_ID, text=text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — список доступных команд."""
    text = (
        "Доступные команды:\n\n"
        "/ping — проверить, что бот живой\n"
        "/channels — список каналов с владельцем и ссылкой\n"
        "/stats — статистика подписчиков по каналам\n"
        "/help — это сообщение\n\n"
        "Бот автоматически отслеживает подписки и отписки "
        "во всех каналах, где он является администратором."
    )
    await update.message.reply_text(text)


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ping — проверка работоспособности бота."""
    await update.message.reply_text("pong")


async def cmd_channels(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/channels — каналы под наблюдением с владельцем и ссылкой."""
    data_dir = Path("data")

    if not data_dir.exists() or not list(data_dir.glob("*.txt")):
        await update.message.reply_text("Пока нет данных ни по одному каналу.")
        return

    lines = ["📋 Каналы под наблюдением:\n"]

    for file in sorted(data_dir.glob("*.txt")):
        try:
            channel_id = int(file.stem)
        except ValueError:
            continue

        # Получаем информацию о канале
        try:
            chat = await context.bot.get_chat(channel_id)
        except Exception:
            lines.append(f"• ID {channel_id} — не удалось получить данные\n")
            continue

        # Ссылка: для публичных каналов — t.me/username,
        # для приватных — t.me/c/{id без префикса -100}
        if chat.username:
            link = f"https://t.me/{chat.username}"
        else:
            short_id = str(channel_id).lstrip("-").removeprefix("100")
            link = f"https://t.me/c/{short_id}"

        # Ищем владельца среди администраторов
        owner_label = "неизвестен"
        try:
            admins = await context.bot.get_chat_administrators(channel_id)
            for admin in admins:
                if admin.status == ChatMember.OWNER:
                    owner_label = _user_label(admin.user)
                    break
        except Exception:
            owner_label = "нет доступа"

        lines.append(
            f"📢 {chat.title}\n"
            f"  Ссылка: {link}\n"
            f"  Владелец: {owner_label}\n"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — статистика по всем известным каналам."""
    data_dir = Path("data")

    if not data_dir.exists() or not list(data_dir.glob("*.txt")):
        await update.message.reply_text("Пока нет данных ни по одному каналу.")
        return

    lines = ["📊 Статистика по каналам:\n"]
    for file in sorted(data_dir.glob("*.txt")):
        try:
            channel_id = int(file.stem)
        except ValueError:
            continue

        stats = storage.get_stats(channel_id)

        try:
            chat = await context.bot.get_chat(channel_id)
            name = _channel_label(chat)
        except Exception:
            name = str(channel_id)

        lines.append(
            f"📢 {name}\n"
            f"  Сейчас подписаны: {stats['active']}\n"
            f"  Всего видели: {stats['total']}\n"
            f"  Бывших подписчиков: {stats['inactive']}\n"
        )

    await update.message.reply_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # chat_member — изменения состава каналов (требует явного указания в allowed_updates)
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("channels", cmd_channels))
    app.add_handler(CommandHandler("stats", cmd_stats))

    logger.info("Бот запущен. Ожидаю события…")
    app.run_polling(allowed_updates=["chat_member", "message"])


if __name__ == "__main__":
    main()
