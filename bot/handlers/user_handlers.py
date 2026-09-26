from maxo import Router

from maxo.fsm import FSMContext, StateFilter
from datetime import datetime, timezone

from maxo.routing.filters import Command, CommandStart
from maxo.types import BotStarted, MessageCallback, MessageCreated

from ..states.user_states import *
from ..keyboards.user_keyboards import *
import utils.parsers as parsers


from data.models import User
from data.crud import get_user_by_id, create_user, set_user_name, set_user_phone, set_user_city
from data import SessionDep

FIELDS = {"name": "Имя", "phone": "Телефон", "city": "Город"}
SETTERS = {"name": set_user_name, "phone": set_user_phone, "city": set_user_city}
STUB = "Раздел в разработке"
NOT_REGISTERED = "Сначала зарегистрируйтесь: /start"

router = Router()


# Текст карточки профиля
def profile_text(user: User) -> str:
    values = {"name": user.name, "phone": user.phone_number, "city": user.city}
    lines = [f"{title}: {values[key]}" for key, title in FIELDS.items()]
    return "Ваш профиль\n\n" + "\n".join(lines)


# Старт: зарегистрированному меню, новому анкета
async def start(user_id: int, send, fsm_context: FSMContext, session: SessionDep) -> None:
    await fsm_context.clear()
    user = await get_user_by_id(user_id, session)
    if user:
        await send(text="Главное меню", keyboard=main_menu_kb())
        return
    await send(text="Как вас зовут?")
    await fsm_context.set_state(REG_NAME)


# Нажатие Начать
@router.bot_started()
async def on_bot_started(event: BotStarted, fsm_context: FSMContext, session: SessionDep) -> None:
    await start(event.user.user_id, event.send_message, fsm_context, session)


# /start
@router.message_created(CommandStart())
async def on_start(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    await start(message.user_id, message.answer, fsm_context, session)


# /menu
@router.message_created(Command("menu"))
async def on_menu(message: MessageCreated, session: SessionDep) -> None:
    user = await get_user_by_id(message.user_id, session)
    if not user:
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
    value, error = parsers.parse_field("name", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(name=value)
    await fsm_context.set_state(REG_PHONE)
    await message.answer("Введите номер телефона")


# Регистрация: телефон
@router.message_created(StateFilter(REG_PHONE))
async def reg_phone(message: MessageCreated, fsm_context: FSMContext) -> None:
    value, error = parsers.parse_field("phone", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(phone=value)
    await fsm_context.set_state(REG_CITY)
    await message.answer("Из какого вы города?")


# Регистрация: город, сохранение пользователя
@router.message_created(StateFilter(REG_CITY))
async def reg_city(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("city", message.text)
    if not value:
        await message.answer(error)
        return
    data = await fsm_context.get_data()
    sender = message.message.sender
    user_name = getattr(sender, "username", None) or getattr(sender, "fullname", None) or str(message.user_id)
    await create_user(User(id=message.user_id, name=data["name"], user_name=user_name, phone_number=data["phone"], city=value, creation_date=datetime.now(timezone.utc)), session)
    await fsm_context.clear()
    await message.answer(text="Регистрация завершена", keyboard=main_menu_kb())



# Все нажатия кнопок.
# В MAX пустой callback_answer() запрещён: нужен notification или message.
# Если сообщение уже отредактировано через edit_message, отвечать не нужно.
@router.message_callback()
async def on_callback(cb: MessageCallback, fsm_context: FSMContext, session: SessionDep) -> None:
    user = await get_user_by_id(cb.user.user_id, session)
    if not user:
        await cb.callback_answer(notification=NOT_REGISTERED)
        return

    payload = cb.payload or ""

    if payload == "menu:main":
        await fsm_context.clear()
        await cb.edit_message(text="Главное меню", keyboard=main_menu_kb())

    elif payload == "menu:profile":
        await fsm_context.clear()
        await cb.edit_message(text=profile_text(user), keyboard=profile_kb())

    elif payload.startswith("edit:"):
        field = payload.split(":", 1)[1]
        if field not in FIELDS:
            await cb.callback_answer(notification="Кнопка устарела, откройте /menu")
            return
        await fsm_context.set_state(EDIT)
        await fsm_context.update_data(field=field)
        kb = KeyboardBuilder().add_callback(text="Отмена", payload="menu:profile").build()
        await cb.edit_message(text=f"Введите новое значение: {FIELDS[field].lower()}", keyboard=kb)

    elif payload.startswith("menu:"):
        await cb.callback_answer(notification=STUB)

    else:
        await cb.callback_answer(notification="Кнопка устарела, откройте /menu")


# Сохранение нового значения поля профиля
@router.message_created(StateFilter(EDIT))
async def edit_value(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    field = await fsm_context.get_value("field")
    value, error = parsers.parse_field(field, message.text)
    if not value:
        await message.answer(error)
        return
    user = await get_user_by_id(message.user_id, session)
    await fsm_context.clear()
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    await SETTERS[field](message.user_id, value, session)
    await message.answer(text=f"Сохранено\n\n{profile_text(user)}", keyboard=profile_kb())


# Любое другое сообщение
@router.message_created()
async def unknown_message(message: MessageCreated, session: SessionDep) -> None:
    user = await get_user_by_id(message.user_id, session)
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    await message.answer(text="Воспользуйтесь меню", keyboard=main_menu_kb())