from datetime import datetime, timezone

from maxo import Router
from maxo.fsm import FSMContext, StateFilter
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotStarted, MessageCallback, MessageCreated
from maxo.enums import TextFormat

from ..states.user_states import REG_NAME, REG_PHONE, REG_CITY, EDIT
from ..keyboards.user_keyboards import main_menu_kb, profile_kb, cancel_edit_kb
import utils.parsers as parsers

from data.models import User
import data.crud as db
from data import SessionDep

FIELDS = {"name": "Имя", "phone": "Телефон", "city": "Город"}
SETTERS = {"name": db.set_user_name, "phone": db.set_user_phone, "city": db.set_user_city}
STUB = "Раздел в разработке"
NOT_REGISTERED = "Сначала зарегистрируйтесь: /start"
OUTDATED = "Кнопка устарела, откройте /menu"

MAIN_MENU_TEXT = """🏠 **Главное меню**

_Ищите идеальное пространство для офиса, мероприятия, общепита или склада. В каждой карточке сразу указаны технические требования, планировка и условия собственника._
━━━━━━━━━━━━━━━
**Смотреть объекты** — полный каталог помещений
**Профиль** — ваши контактные данные и настройки
**Мои объекты** — управление размещенными объявлениями
**Избранное** — сохраненные варианты для быстрого доступа
**Помощь** — ответы на частые вопросы и связь с поддержкой

Нажмите нужный раздел:"""

router = Router()


def profile_text(user: User) -> str:
    name = parsers.md(user.name)
    phone = parsers.md(user.phone_number)
    city = parsers.md(user.city)

    return (f'''**👤 Ваш профиль**

**Имя:** {name}
**Телефон:** `{phone}`
**Город:** {city}
        
⚠️ _**Важно:** вводите актуальные данные, они буду предоставляться людям, с которыми вы захотите связатьсяю_''')


# Старт: зарегистрированному меню, новому анкета
async def start(user_id: int, send, fsm_context: FSMContext, session: SessionDep) -> None:
    await fsm_context.clear()
    user = await db.get_user_by_id(user_id, session)
    if user:
        await send(text=MAIN_MENU_TEXT, keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)
        return
    await send(text='''📝 **Регистрация**
    
**Шаг 1/3.** Укажите ваше имя:''', format=TextFormat.MARKDOWN)
    await fsm_context.set_state(REG_NAME)


# Нажатие «Начать»
@router.bot_started()
async def on_bot_started(event: BotStarted, fsm_context: FSMContext, session: SessionDep) -> None:
    await start(event.user.user_id, event.send_message, fsm_context, session)


# /start
@router.message_created(CommandStart())
async def on_start(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    await start(message.user_id, message.answer, fsm_context, session)


# /menu
@router.message_created(Command("menu"))
async def on_menu(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    user = await db.get_user_by_id(message.user_id, session)
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    await fsm_context.clear()
    await message.answer(text=MAIN_MENU_TEXT, keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)


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
    await message.answer(text='''📝 **Регистрация**
    
**Шаг 2/3.** Укажите ваш номер телефона в формате +7XXXXXXXXXX:''', format=TextFormat.MARKDOWN)


# Регистрация: телефон
@router.message_created(StateFilter(REG_PHONE))
async def reg_phone(message: MessageCreated, fsm_context: FSMContext) -> None:
    value, error = parsers.parse_field("phone", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(phone=value)
    await fsm_context.set_state(REG_CITY)
    await message.answer(text='''📝 **Регистрация**
    
**Шаг 3/3.** Укажите ваш город:''', format=TextFormat.MARKDOWN)


# Регистрация: город, сохранение пользователя
@router.message_created(StateFilter(REG_CITY))
async def reg_city(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("city", message.text)
    if not value:
        await message.answer(error)
        return
    data = await fsm_context.get_data()
    sender = message.message.sender
    user_name = (
        getattr(sender, "username", None)
        or getattr(sender, "fullname", None)
        or str(message.user_id)
    )
    await db.create_user(
        User(
            id=message.user_id,
            name=data["name"],
            user_name=user_name,
            phone_number=data["phone"],
            city=value,
            creation_date=datetime.now(timezone.utc),
        ),
        session,
    )
    await fsm_context.clear()
    await message.answer(text=f"Регистрация завершена\n\n{MAIN_MENU_TEXT}", keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)


# Все нажатия кнопок.
# В MAX пустой callback_answer() запрещён: нужен notification или message.
# Если сообщение уже отредактировано через edit_message, отвечать не нужно.
@router.message_callback()
async def on_callback(cb: MessageCallback, fsm_context: FSMContext, session: SessionDep) -> None:
    user = await db.get_user_by_id(cb.user.user_id, session)
    if not user:
        await cb.callback_answer(notification=NOT_REGISTERED)
        return

    payload = cb.payload or ""

    if payload == "menu:main":
        await fsm_context.clear()
        await cb.edit_message(text=MAIN_MENU_TEXT, keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)

    elif payload == "menu:profile":
        await fsm_context.clear()
        await cb.edit_message(text=profile_text(user), keyboard=profile_kb(), format=TextFormat.MARKDOWN)

    elif payload.startswith("edit:"):
        field = payload.split(":", 1)[1]
        if field not in FIELDS:
            await cb.callback_answer(notification=OUTDATED)
            return
        await fsm_context.set_state(EDIT)
        await fsm_context.update_data(field=field)
        await cb.edit_message(text=f'''Изменение параметра **{FIELDS[field].lower()}**
        
Введите новое значение:''',
            keyboard=cancel_edit_kb(), format=TextFormat.MARKDOWN)

    elif payload.startswith("menu:"):
        await cb.callback_answer(notification=STUB)

    else:
        await cb.callback_answer(notification=OUTDATED)


# Сохранение нового значения поля профиля
@router.message_created(StateFilter(EDIT))
async def edit_value(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    field = await fsm_context.get_value("field")
    if field not in FIELDS:
        await fsm_context.clear()
        await message.answer(OUTDATED)
        return

    value, error = parsers.parse_field(field, message.text)
    if not value:
        await message.answer(error)
        return

    if not await db.get_user_by_id(message.user_id, session):
        await fsm_context.clear()
        await message.answer(NOT_REGISTERED)
        return

    await SETTERS[field](message.user_id, value, session)
    await fsm_context.clear()

    # Перечитываем пользователя, чтобы показать уже обновлённые данные
    user = await db.get_user_by_id(message.user_id, session)
    await message.answer(text=f"Сохранено\n\n{profile_text(user)}", keyboard=profile_kb(), format=TextFormat.MARKDOWN)


# Любое другое сообщение
@router.message_created()
async def unknown_message(message: MessageCreated, session: SessionDep) -> None:
    user = await db.get_user_by_id(message.user_id, session)
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    await message.answer(text="Воспользуйтесь меню", keyboard=main_menu_kb())