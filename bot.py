"""
MPrimeTranslate_1Bot
A Telegram translation bot similar to LanguageTranslatorBot.

Features
--------
- /start, /help          - onboarding
- /setlang <code>        - set your default target language (e.g. /setlang fr)
- /lang                  - show your current target language
- /langs                 - list supported language codes
- /detect <text>         - detect the language of a piece of text
- /translate <code> text - one-off translation into a specific language
- Plain text message     - auto-translated into your saved target language
- Inline mode (@BotName text) - translate on the fly inside any chat

Storage
-------
Per-user target-language preferences are kept in a small local JSON file
(user_prefs.json). This is fine for a single Railway instance / low traffic.
If you need durability across redeploys or multiple instances, swap
`storage.py` for a real database (Postgres/Redis) - Railway can host both.
"""

import logging
import os
import uuid

from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from storage import get_user_lang, set_user_lang

# Deterministic language detection results
DetectorFactory.seed = 0

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DEFAULT_TARGET_LANG = "en"

# A trimmed, friendly list shown by /langs (deep-translator supports far more;
# see /langs output which pulls the full live list too).
POPULAR_LANGS = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "zh-CN": "Chinese (Simplified)",
    "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi",
    "tr": "Turkish", "nl": "Dutch", "pl": "Polish", "sv": "Swedish",
    "vi": "Vietnamese", "th": "Thai", "id": "Indonesian", "uk": "Ukrainian",
}


def translate_text(text: str, target: str, source: str = "auto") -> str:
    """Translate text using deep-translator's Google engine."""
    return GoogleTranslator(source=source, target=target).translate(text)


# --------------------------------------------------------------------------
# Command handlers
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Hi! I'm *MPrimeTranslate_1Bot*.\n\n"
        "Send me any text and I'll translate it into your target language "
        "(default: English).\n\n"
        "Useful commands:\n"
        "• /setlang `fr` — set your default target language\n"
        "• /lang — show your current target language\n"
        "• /translate `de` `Hello there` — one-off translation\n"
        "• /detect `Bonjour` — detect a language\n"
        "• /langs — list common language codes\n\n"
        "You can also use me *inline* in any chat: type `@MPrimeTranslate_1Bot hello`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: /setlang <language_code>\nExample: /setlang es"
        )
        return
    code = context.args[0].lower()
    set_user_lang(update.effective_user.id, code)
    name = POPULAR_LANGS.get(code, code)
    await update.message.reply_text(f"✅ Your target language is now set to *{name}* (`{code}`).",
                                     parse_mode=ParseMode.MARKDOWN)


async def show_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    code = get_user_lang(update.effective_user.id, DEFAULT_TARGET_LANG)
    name = POPULAR_LANGS.get(code, code)
    await update.message.reply_text(f"🌐 Your current target language: *{name}* (`{code}`)",
                                     parse_mode=ParseMode.MARKDOWN)


async def list_langs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"`{code}` – {name}" for code, name in sorted(POPULAR_LANGS.items())]
    await update.message.reply_text(
        "🌍 *Common language codes:*\n" + "\n".join(lines) +
        "\n\nMany more ISO codes are supported — just try /setlang <code>.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def detect_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /detect <text>")
        return
    try:
        code = detect(text)
        name = POPULAR_LANGS.get(code, code)
        await update.message.reply_text(f"🔎 Detected language: *{name}* (`{code}`)",
                                         parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.exception("detect failed")
        await update.message.reply_text(f"⚠️ Couldn't detect language: {e}")


async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /translate <target_code> <text>")
        return
    target = context.args[0].lower()
    text = " ".join(context.args[1:])
    try:
        result = translate_text(text, target)
        await update.message.reply_text(result)
    except Exception as e:
        logger.exception("translate_cmd failed")
        await update.message.reply_text(f"⚠️ Translation failed: {e}")


async def translate_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if not text:
        return
    target = get_user_lang(update.effective_user.id, DEFAULT_TARGET_LANG)
    try:
        result = translate_text(text, target)
        await update.message.reply_text(result)
    except Exception as e:
        logger.exception("translate_plain_text failed")
        await update.message.reply_text(f"⚠️ Translation failed: {e}")


# --------------------------------------------------------------------------
# Inline mode: "@MPrimeTranslate_1Bot hello" -> offers translations
# --------------------------------------------------------------------------

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query
    if not query:
        return

    targets = ["en", "es", "fr", "de", "ru"]
    results = []
    for code in targets:
        try:
            translated = translate_text(query, code)
        except Exception:
            continue
        name = POPULAR_LANGS.get(code, code)
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"→ {name}",
                description=translated,
                input_message_content=InputTextMessageContent(translated),
            )
        )
    await update.inline_query.answer(results, cache_time=1)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set. "
            "Get a token from @BotFather and set it in your environment / Railway variables."
        )

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("setlang", set_lang))
    application.add_handler(CommandHandler("lang", show_lang))
    application.add_handler(CommandHandler("langs", list_langs))
    application.add_handler(CommandHandler("detect", detect_lang))
    application.add_handler(CommandHandler("translate", translate_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_plain_text))
    application.add_handler(InlineQueryHandler(inline_query))

    logger.info("Bot starting (polling mode)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
