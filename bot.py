import asyncio
import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
CONTACT_URL = "https://t.me/nataliia_catpsy_pro"

dp = Dispatcher(storage=MemoryStorage())

# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def button(text, callback_data=None, url=None):
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        url=url,
    )


def keyboard(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def edit(callback: CallbackQuery, text: str, reply_markup):
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
    )
    await callback.answer()


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu():
    return keyboard([
        [button("🐾 Рассказать о проблеме", callback_data="problems")],
        [button("💬 Написать мне напрямую", url=CONTACT_URL)],
        [button("ℹ️ Как проходит консультация", callback_data="consultation")],
    ])


def problems_menu():
    return keyboard([
        [button("🚽 Проблемы с лотком", callback_data="category:toilet")],
        [button("😾 Агрессия", callback_data="category:aggression")],
        [button("🙀 Страх и тревожность", callback_data="category:fear")],
        [button("🐈 Отношения между кошками", callback_data="category:cats")],
        [button("🛋 Порча мебели", callback_data="category:furniture")],
        [button("🌙 Ночное хулиганство", callback_data="category:night")],
        [button("🗣 Повышенная вокализация", callback_data="category:vocalization")],
        [button("🏠 Переезд и адаптация", callback_data="category:adaptation")],
        [button("❓ Другая ситуация", callback_data="category:other")],
        [button("💬 Сразу написать мне", url=CONTACT_URL)],
        [button("← Назад", callback_data="main")],
    ])


def exit_buttons(back_callback):
    return [
        [button("💬 Сразу написать мне", url=CONTACT_URL)],
        [button("← Назад", callback_data=back_callback)],
    ]


def submitted_menu():
    return keyboard([
        [button("🐾 Рассказать о другой проблеме", callback_data="problems")],
        [button("🏠 В главное меню", callback_data="main")],
    ])


def contact_request_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="📱 Поделиться номером телефона",
                request_contact=True,
            )],
            [KeyboardButton(text="💬 Написать Наталии самостоятельно")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# =========================================================
# ДАННЫЕ ДЛЯ ВЕТОК
# =========================================================

CATEGORIES = {
    "toilet": {
        "name": "🚽 Проблемы с лотком",
        "question": "Что именно происходит?",
        "options": [
            ("💧 Мочится вне лотка", "toilet_pee"),
            ("💩 Оставляет кал вне лотка", "toilet_poop"),
            ("🚽 И то и другое", "toilet_both"),
            ("🐾 Не хочет / боится пользоваться лотком", "toilet_avoid"),
            ("❓ Другая проблема с лотком", "toilet_other"),
        ],
        "ask_duration": True,
        "ask_vet": True,
    },

    "aggression": {
        "name": "😾 Агрессия",
        "question": "На кого направлена агрессия?",
        "options": [
            ("👤 На людей", "aggr_people"),
            ("🐈 На другую кошку", "aggr_cat"),
            ("🐕 На другое животное", "aggr_animal"),
            ("😾 На нескольких / всех", "aggr_everyone"),
            ("❓ Сложно определить", "aggr_unknown"),
        ],
        "ask_duration": True,
        "ask_vet": True,
    },

    "fear": {
        "name": "🙀 Страх и тревожность",
        "question": "Как это проявляется?",
        "options": [
            ("🫥 Прячется / избегает контакта", "fear_hide"),
            ("🙀 Боится людей", "fear_people"),
            ("🔊 Боится звуков или предметов", "fear_sounds"),
            ("😿 Тревожится, когда остаётся одна", "fear_alone"),
            ("🏠 Боится определённых ситуаций", "fear_situations"),
            ("❓ Другое", "fear_other"),
        ],
        "ask_duration": True,
        "ask_vet": False,
    },

    "cats": {
        "name": "🐈 Отношения между кошками",
        "question": "Что происходит между кошками?",
        "options": [
            ("😾 Дерутся / нападают друг на друга", "cats_fight"),
            ("👀 Одна преследует другую", "cats_chase"),
            ("🙀 Одна кошка боится другой", "cats_fear"),
            ("🚧 Не могут спокойно находиться рядом", "cats_tension"),
            ("🐱 Нужно познакомить новую кошку", "cats_introduction"),
            ("❓ Сложно определить", "cats_unknown"),
        ],
        "ask_duration": True,
        "ask_vet": False,
        "skip_duration_for": ["cats_introduction"],
    },

    "furniture": {
        "name": "🛋 Порча мебели",
        "question": "Что именно делает кошка?",
        "options": [
            ("🐾 Царапает мягкую мебель", "furniture_soft"),
            ("🪵 Царапает деревянную мебель", "furniture_wood"),
            ("🧱 Царапает стены / обои", "furniture_walls"),
            ("🦷 Грызёт мебель или предметы интерьера", "furniture_bite"),
            ("❓ Другое", "furniture_other"),
        ],
        "ask_duration": True,
        "ask_vet": False,
    },

    "night": {
        "name": "🌙 Ночное хулиганство",
        "question": "Что чаще всего происходит ночью?",
        "options": [
            ("🏃 Бегает / играет / шумит", "night_play"),
            ("😼 Будит вас", "night_wake"),
            ("🚪 Скребётся в дверь", "night_door"),
            ("🐾 Требует внимания", "night_attention"),
            ("🍽 Требует еду", "night_food"),
            ("❓ Другое", "night_other"),
        ],
        "ask_duration": True,
        "ask_vet": False,
    },

    "vocalization": {
        "name": "🗣 Повышенная вокализация",
        "question": "Когда кошка чаще всего мяукает?",
        "options": [
            ("🌙 Ночью", "voice_night"),
            ("☀️ Днём", "voice_day"),
            ("🚪 Когда остаётся одна", "voice_alone"),
            ("👤 Когда рядом человек", "voice_person"),
            ("🍽 Когда хочет еду", "voice_food"),
            ("🗣 В разное время / почти постоянно", "voice_always"),
            ("❓ Сложно определить", "voice_unknown"),
        ],
        "ask_duration": True,
        "ask_vet": True,
    },

    "adaptation": {
        "name": "🏠 Переезд и адаптация",
        "question": "Какая у вас ситуация?",
        "options": [
            ("📦 Только готовимся к переезду", "adapt_moving"),
            ("🏠 Недавно переехали с кошкой", "adapt_moved"),
            ("🐱 Кошка недавно появилась в новом доме", "adapt_new_cat"),
            ("🐈 В доме появилась новая кошка", "adapt_second_cat"),
            ("🐕 Появилось другое животное", "adapt_animal"),
            ("👤 В доме появился новый человек", "adapt_person"),
            ("❓ Другая ситуация", "adapt_other"),
        ],
        "ask_duration": False,
        "ask_vet": False,
    },
}


DURATIONS = [
    ("Последние несколько дней", "duration_days"),
    ("Несколько недель", "duration_weeks"),
    ("Несколько месяцев", "duration_months"),
    ("Больше года", "duration_year"),
    ("Так было всегда", "duration_always"),
    ("Сложно сказать", "duration_unknown"),
]


VET_OPTIONS = [
    ("🩺 Да", "vet_yes"),
    ("📅 Записались / планируем", "vet_planned"),
    ("❌ Нет", "vet_no"),
]


# Создаём быстрый поиск ответа по callback_data
OPTION_LOOKUP = {}

for category_id, category in CATEGORIES.items():
    for label, option_id in category["options"]:
        OPTION_LOOKUP[option_id] = (category_id, label)

DURATION_LOOKUP = {option_id: label for label, option_id in DURATIONS}
VET_LOOKUP = {option_id: label for label, option_id in VET_OPTIONS}


# =========================================================
# ЭКРАНЫ
# =========================================================

async def show_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await edit(
        callback,
        "Здравствуйте! 🐾\n\n"
        "Я Catpsy Assistant — помощник котопсихолога.\n\n"
        "Здесь можно немного рассказать о ситуации с вашей кошкой, "
        "узнать, как проходит консультация или сразу написать мне напрямую.",
        main_menu(),
    )


async def show_problems(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await edit(
        callback,
        "Что вас беспокоит? 🐾\n\n"
        "Выберите наиболее подходящий вариант. "
        "Если ситуация сложная или подходящего пункта нет — "
        "можно сразу написать мне.",
        problems_menu(),
    )


async def show_category(callback: CallbackQuery, state: FSMContext, category_id: str):
    category = CATEGORIES[category_id]

    await state.set_data({
        "category": category_id,
        "category_name": category["name"],
    })

    rows = []

    for label, option_id in category["options"]:
        rows.append([
            button(label, callback_data=f"answer:{option_id}")
        ])

    rows.extend(exit_buttons("problems"))

    await edit(
        callback,
        f"{category['name']}\n\n"
        f"{category['question']}",
        keyboard(rows),
    )


async def show_duration(callback: CallbackQuery):
    rows = []

    for label, option_id in DURATIONS:
        rows.append([
            button(label, callback_data=f"duration:{option_id}")
        ])

    rows.extend(exit_buttons("back_category"))

    await edit(
        callback,
        "Когда это началось?",
        keyboard(rows),
    )


async def show_vet(callback: CallbackQuery):
    rows = []

    for label, option_id in VET_OPTIONS:
        rows.append([
            button(label, callback_data=f"vet:{option_id}")
        ])

    rows.extend(exit_buttons("back_duration"))

    await edit(
        callback,
        "После появления проблемы кошку осматривал ветеринар?",
        keyboard(rows),
    )


async def send_application(bot: Bot, user, state: FSMContext, phone: str | None = None):
    if not ADMIN_CHAT_ID:
        return False

    data = await state.get_data()

    lines = [
        "🐾 Новая заявка",
        "",
        f"Имя: {user.full_name}",
    ]

    if user.username:
        lines.append(f"Telegram: @{user.username}")
    if phone:
        lines.append(f"Телефон: {phone}")

    lines.extend([
        f"Telegram ID: {user.id}",
        "",
        f"Проблема: {data.get('category_name', '—')}",
        f"Уточнение: {data.get('detail', '—')}",
    ])

    if data.get("duration"):
        lines.append(f"Когда началось: {data['duration']}")
    if data.get("vet"):
        lines.append(f"Осмотр ветеринара: {data['vet']}")

    try:
        await bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text="\n".join(lines),
        )
    except (ValueError, TypeError, TelegramAPIError):
        return False

    return True


async def show_finish(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user

    if user.username:
        sent = await send_application(callback.bot, user, state)

        if sent:
            await state.clear()
            await edit(
                callback,
                "Спасибо! Заявка отправлена 🐾\n\n"
                "Я передал Наталии информацию о вашей ситуации. "
                "Она напишет вам в Telegram, чтобы уточнить детали "
                "и договориться о консультации.",
                submitted_menu(),
            )
        else:
            await edit(
                callback,
                "Не получилось автоматически отправить заявку.\n\n"
                "Пожалуйста, напишите Наталии напрямую — "
                "так ваша заявка точно не потеряется.",
                keyboard([
                    [button("💬 Написать Наталии", url=CONTACT_URL)],
                    [button("🏠 В главное меню", callback_data="main")],
                ]),
            )
        return

    await edit(
        callback,
        "Остался последний шаг 🐾\n\n"
        "У вас не указан username в Telegram, поэтому нужен контакт, "
        "по которому Наталия сможет с вами связаться.\n\n"
        "Можно поделиться номером телефона или написать Наталии самостоятельно.",
        None,
    )

    await callback.message.answer(
        "Выберите удобный вариант:",
        reply_markup=contact_request_keyboard(),
    )


# =========================================================
# /START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Здравствуйте! 🐾\n\n"
        "Я Catpsy Assistant — помощник котопсихолога.\n\n"
        "Здесь можно немного рассказать о ситуации с вашей кошкой, "
        "узнать, как проходит консультация или сразу написать мне напрямую.",
        reply_markup=main_menu(),
    )


# =========================================================
# ОСНОВНАЯ НАВИГАЦИЯ
# =========================================================

@dp.callback_query(F.data == "main")
async def main_callback(callback: CallbackQuery, state: FSMContext):
    await show_main(callback, state)


@dp.callback_query(F.data == "problems")
async def problems_callback(callback: CallbackQuery, state: FSMContext):
    await show_problems(callback, state)


@dp.callback_query(F.data == "consultation")
async def consultation_callback(callback: CallbackQuery):
    await edit(
        callback,
        "ℹ️ Как проходит консультация\n\n"
        "Перед консультацией я знакомлюсь с вашей ситуацией и материалами, "
        "которые вы присылаете.\n\n"
        "На консультации мы подробно разбираем причины поведения кошки "
        "и определяем, что можно изменить.\n\n"
        "После встречи вы получаете письменные рекомендации.",
        keyboard([
            [button("💬 Написать мне", url=CONTACT_URL)],
            [button("← Назад", callback_data="main")],
        ]),
    )


# =========================================================
# ВЫБОР КАТЕГОРИИ
# =========================================================

@dp.callback_query(F.data.startswith("category:"))
async def category_callback(callback: CallbackQuery, state: FSMContext):
    category_id = callback.data.split(":", 1)[1]

    if category_id == "other":
        await state.clear()

        await edit(
            callback,
            "❓ Другая ситуация\n\n"
            "Не нашли подходящего варианта?\n\n"
            "Ничего страшного — напишите мне и расскажите своими словами, "
            "что происходит с кошкой.",
            keyboard([
                [button("💬 Написать мне", url=CONTACT_URL)],
                [button("← Назад", callback_data="problems")],
            ]),
        )
        return

    await show_category(callback, state, category_id)


# =========================================================
# ОТВЕТ НА УТОЧНЯЮЩИЙ ВОПРОС
# =========================================================

@dp.callback_query(F.data.startswith("answer:"))
async def answer_callback(callback: CallbackQuery, state: FSMContext):
    option_id = callback.data.split(":", 1)[1]

    if option_id not in OPTION_LOOKUP:
        await callback.answer()
        return

    category_id, answer_label = OPTION_LOOKUP[option_id]
    category = CATEGORIES[category_id]

    await state.update_data(
        category=category_id,
        category_name=category["name"],
        detail_id=option_id,
        detail=answer_label,
    )

    # Исключение: знакомство новой кошки
    if option_id in category.get("skip_duration_for", []):
        await show_finish(callback, state)
        return

    if category["ask_duration"]:
        await show_duration(callback)
        return

    if category["ask_vet"]:
        await show_vet(callback)
        return

    await show_finish(callback, state)


# =========================================================
# КОГДА НАЧАЛОСЬ
# =========================================================

@dp.callback_query(F.data.startswith("duration:"))
async def duration_callback(callback: CallbackQuery, state: FSMContext):
    option_id = callback.data.split(":", 1)[1]

    if option_id not in DURATION_LOOKUP:
        await callback.answer()
        return

    await state.update_data(
        duration_id=option_id,
        duration=DURATION_LOOKUP[option_id],
    )

    data = await state.get_data()
    category_id = data.get("category")

    if not category_id:
        await show_problems(callback, state)
        return

    category = CATEGORIES[category_id]

    if category["ask_vet"]:
        await show_vet(callback)
        return

    await show_finish(callback, state)


# =========================================================
# ВЕТЕРИНАР
# =========================================================

@dp.callback_query(F.data.startswith("vet:"))
async def vet_callback(callback: CallbackQuery, state: FSMContext):
    option_id = callback.data.split(":", 1)[1]

    if option_id not in VET_LOOKUP:
        await callback.answer()
        return

    await state.update_data(
        vet_id=option_id,
        vet=VET_LOOKUP[option_id],
    )

    await show_finish(callback, state)


# =========================================================
# КОНТАКТ ДЛЯ ЗАЯВКИ
# =========================================================

@dp.message(F.contact)
async def contact_callback(message: Message, state: FSMContext):
    contact = message.contact

    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "Пожалуйста, поделитесь именно своим контактом с помощью кнопки ниже.",
            reply_markup=contact_request_keyboard(),
        )
        return

    sent = await send_application(
        message.bot,
        message.from_user,
        state,
        phone=contact.phone_number,
    )

    if sent:
        await state.clear()
        await message.answer(
            "Спасибо! Заявка отправлена 🐾\n\n"
            "Я передал Наталии информацию о вашей ситуации. "
            "Она свяжется с вами, чтобы уточнить детали "
            "и договориться о консультации.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await message.answer(
            "Что хотите сделать дальше?",
            reply_markup=submitted_menu(),
        )
    else:
        await message.answer(
            "Не получилось автоматически отправить заявку. "
            "Пожалуйста, напишите Наталии напрямую.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await message.answer(
            "Открыть Telegram Наталии:",
            reply_markup=keyboard([
                [button("💬 Написать Наталии", url=CONTACT_URL)],
                [button("🏠 В главное меню", callback_data="main")],
            ]),
        )


@dp.message(F.text == "💬 Написать Наталии самостоятельно")
async def direct_contact_from_request(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Хорошо 🐾 Нажмите кнопку ниже, чтобы написать Наталии напрямую.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Telegram Наталии:",
        reply_markup=keyboard([
            [button("💬 Написать Наталии", url=CONTACT_URL)],
            [button("🏠 В главное меню", callback_data="main")],
        ]),
    )


# =========================================================
# КНОПКИ "НАЗАД"
# =========================================================

@dp.callback_query(F.data == "back_category")
async def back_category(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category_id = data.get("category")

    if not category_id:
        await show_problems(callback, state)
        return

    await show_category(callback, state, category_id)


@dp.callback_query(F.data == "back_duration")
async def back_duration(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    category_id = data.get("category")

    if not category_id:
        await show_problems(callback, state)
        return

    category = CATEGORIES[category_id]

    if category["ask_duration"]:
        await show_duration(callback)
    else:
        await show_category(callback, state, category_id)


# =========================================================
# ЗАПУСК
# =========================================================

if not TOKEN:
    raise ValueError("Не найден BOT_TOKEN")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "10000"))

bot = Bot(token=TOKEN)

async def on_startup(bot: Bot):
    if not WEBHOOK_URL:
        raise ValueError("Не найден WEBHOOK_URL")
    if not ADMIN_CHAT_ID:
        raise ValueError("Не найден ADMIN_CHAT_ID")

    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")


async def on_shutdown(bot: Bot):
    await bot.session.close()

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

app = web.Application()

SimpleRequestHandler(
    dispatcher=dp,
    bot=bot,
).register(app, path=WEBHOOK_PATH)

setup_application(app, dp, bot=bot)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)