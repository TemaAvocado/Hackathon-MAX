import re

from config import BOT_TOKEN
from maxo import Bot, Dispatcher, Router
from maxo.fsm import FSMContext, State, StateFilter
from maxo.fsm.storages.memory import MemoryStorage
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotCommand, BotStarted, MessageCallback, MessageCreated
from maxo.utils.builders import KeyboardBuilder

# Состояния сценариев
REG_NAME = State("reg_name")
REG_PHONE = State("reg_phone")
REG_CITY = State("reg_city")
EDIT = State("edit")

# Заглушка вместо БД
USERS: dict[int, dict[str, str]] = {}

FIELDS = {"name": "Имя", "phone": "Телефон", "city": "Город"}
STUB = "Раздел в разработке"
NOT_REGISTERED = "Сначала зарегистрируйтесь: /start"

router = Router()


# Приводит телефон к виду +7XXXXXXXXXX
def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return "+" + digits if 11 <= len(digits) <= 15 else None


# Проверяет ввод поля
def parse_field(field: str, text: str | None) -> tuple[str | None, str]:
    text = (text or "").strip()
    if field == "phone":
        phone = normalize_phone(text)
        return (phone, "") if phone else (None, "Введите номер в формате +79991234567")
    if not text:
        return None, "Отправьте текстом"
    if len(text) > 64:
        return None, "Максимум 64 символа"
    return text, ""


# Клавиатура главного меню
def main_menu_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="Открыть приложение", payload="menu:app")
        .add_callback(text="Профиль", payload="menu:profile")
        .add_callback(text="Мои объекты", payload="menu:objects")
        .add_callback(text="Избранное", payload="menu:favorites")
        .add_callback(text="Помощь", payload="menu:help")
        .adjust(1, 2, 2)
        .build()
    )


# Клавиатура профиля
def profile_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="Изменить имя", payload="edit:name")
        .add_callback(text="Изменить телефон", payload="edit:phone")
        .add_callback(text="Изменить город", payload="edit:city")
        .add_callback(text="В меню", payload="menu:main")
        .adjust(1)
        .build()
    )


# Текст карточки профиля
def profile_text(user: dict[str, str]) -> str:
    lines = [f"{title}: {user[key]}" for key, title in FIELDS.items()]
    return "Ваш профиль" + "\n".join(lines)


# Нижнее меню, команды бота у поля ввода
@router.after_startup()
async def set_commands(bot: Bot) -> None:
    await bot.edit_bot_info(commands=[
        BotCommand(name="map", description="Карта"),
        BotCommand(name="objects", description="Мои объекты"),
        BotCommand(name="favorites", description="Избранное"),
    ])


# Старт: зарегистрированному меню, новому анкета
async def start(user_id: int, send, fsm_context: FSMContext) -> None:
    await fsm_context.clear()
    user = USERS.get(user_id)
    if user:
        await send(keyboard=main_menu_kb())
        return
    await send(text="Как вас зовут?")
    await fsm_context.set_state(REG_NAME)


# Нажатие Начать
@router.bot_started()
async def on_bot_started(event: BotStarted, fsm_context: FSMContext) -> None:
    await start(event.user.user_id, event.send_message, fsm_context)


# /start
@router.message_created(CommandStart())
async def on_start(message: MessageCreated, fsm_context: FSMContext) -> None:
    await start(message.user_id, message.answer, fsm_context)


# /menu
@router.message_created(Command("menu"))
async def on_menu(message: MessageCreated) -> None:
    if not USERS.get(message.user_id):
        await message.answer(NOT_REGISTERED)
        return
    await message.answer(text="Главное меню", keyboard=main_menu_kb())


# Заглушка нижнего меню
@router.message_created(Command("map", "objects", "favorites"))
async def on_bottom_menu(message: MessageCreated) -> None:
    await message.answer(STUB)


# Регистрация: имя
@router.message_created(StateFilter(REG_NAME))
async def reg_name(message: MessageCreated, fsm_context: FSMContext) -> None:
    value, error = parse_field("name", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(name=value)
    await fsm_context.set_state(REG_PHONE)
    await message.answer("Введите номер телефона")


# Регистрация: телефон
@router.message_created(StateFilter(REG_PHONE))
async def reg_phone(message: MessageCreated, fsm_context: FSMContext) -> None:
    value, error = parse_field("phone", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(phone=value)
    await fsm_context.set_state(REG_CITY)
    await message.answer("Из какого вы города?")


# Регистрация: город, сохранение пользователя
@router.message_created(StateFilter(REG_CITY))
async def reg_city(message: MessageCreated, fsm_context: FSMContext) -> None:
    value, error = parse_field("city", message.text)
    if not value:
        await message.answer(error)
        return
    data = await fsm_context.get_data()
    USERS[message.user_id] = {"name": data["name"], "phone": data["phone"], "city": value}
    await fsm_context.clear()
    await message.answer(text="Регистрация завершена", keyboard=main_menu_kb())


# Все нажатия кнопок
@router.message_callback()
async def on_callback(cb: MessageCallback, fsm_context: FSMContext) -> None:
    user = USERS.get(cb.user.user_id)
    if not user:
        await cb.callback_answer(notification=NOT_REGISTERED)
        return

    payload = cb.payload
    if payload == "menu:main":
        await fsm_context.clear()
        await cb.edit_message(text="Главное меню", keyboard=main_menu_kb())
    elif payload == "menu:profile":
        await fsm_context.clear()
        await cb.edit_message(text=profile_text(user), keyboard=profile_kb())
    elif payload.startswith("edit:"):
        field = payload.split(":")[1]
        await fsm_context.set_state(EDIT)
        await fsm_context.update_data(field=field)
        kb = KeyboardBuilder().add_callback(text="Отмена", payload="menu:profile").build()
        await cb.edit_message(text=f"Введите новое значение: {FIELDS[field].lower()}", keyboard=kb)
    else:
        await cb.callback_answer(notification=STUB)
        return

    await cb.callback_answer()


# Сохранение нового значения поля профиля
@router.message_created(StateFilter(EDIT))
async def edit_value(message: MessageCreated, fsm_context: FSMContext) -> None:
    field = await fsm_context.get_value("field")
    value, error = parse_field(field, message.text)
    if not value:
        await message.answer(error)
        return
    user = USERS.get(message.user_id)
    await fsm_context.clear()
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    user[field] = value
    await message.answer(text=f"Сохранено\n\n{profile_text(user)}", keyboard=profile_kb())


# Любое другое сообщение
@router.message_created()
async def unknown_message(message: MessageCreated) -> None:
    if not USERS.get(message.user_id):
        await message.answer(NOT_REGISTERED)
        return
    await message.answer(text="Воспользуйтесь меню", keyboard=main_menu_kb())


# Кнопка без обработчика
@router.message_callback()
async def unknown_callback(cb: MessageCallback) -> None:
    await cb.callback_answer(notification="Кнопка устарела, откройте /menu")


if __name__ == "__main__":
    dp = Dispatcher(storage=MemoryStorage())
    dp.include(router)
    dp.run_polling(Bot(BOT_TOKEN))
