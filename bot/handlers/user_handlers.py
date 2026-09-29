from datetime import datetime, timezone
from pathlib import Path

from maxo import Router
from maxo.fsm import FSMContext, StateFilter
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotStarted, MessageCallback, MessageCreated, PhotoAttachmentRequest, PhotoAttachmentRequestPayload
from maxo.enums import TextFormat

from ..states.user_states import REG_NAME, REG_PHONE, REG_CITY, EDIT, NO_CREATED_OBJECTS, OBJECT_SET_CITY, OBJECT_SET_ADDRESS, OBJECT_SET_DESCRIPTION, OBJECT_LOAD_PHOTO, OBJECT_LOAD_DOCUMENTS, OBJECT_SET_PRICE, OBJECT_CONFIRM
from ..keyboards.user_keyboards import main_menu_kb, profile_kb, cancel_edit_kb, no_created_objects_kb, cities_kb, cancel_object_creation_kb, confirm_object_creation_kb, city_objects_kb, my_objects_kb, place_kb
import utils.parsers as parsers
import utils.utils as utils
from config import USERS_FILES_FOLDER_PATH

from data.models import User, Place
import data.crud as db
from data import SessionDep

FIELDS = {"name": "Имя", "phone": "Телефон", "city": "Город"}
SETTERS = {"name": db.set_user_name, "phone": db.set_user_phone, "city": db.set_user_city}
STUB = "Раздел в разработке"
NOT_REGISTERED = "Сначала зарегистрируйтесь: /start"
OUTDATED = "Кнопка устарела, откройте /menu"
PAGE_SIZE = 5
MAX_OBJECTS = 6

NO_CREATED_OBJECTS_TEXT = """У вас пока нет созданных объектов. хотите создать новый?"""

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

# Создание объекта: ввод адреса
@router.message_created(StateFilter(OBJECT_SET_ADDRESS))
async def object_set_address(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("address", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(address=value)
    await fsm_context.set_state(OBJECT_SET_DESCRIPTION)
    await message.answer("Введите описание", keyboard=cancel_object_creation_kb())

# Создание объекта: ввод описания
@router.message_created(StateFilter(OBJECT_SET_DESCRIPTION))
async def object_set_description(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("description", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(description=value)
    await fsm_context.set_state(OBJECT_LOAD_PHOTO)
    await message.answer("Загрузите фото (Максимум 5, если вы загрузите больше, примутся только первые 5)", keyboard=cancel_object_creation_kb())

# Создание объекта: ввод фото
@router.message_created(StateFilter(OBJECT_LOAD_PHOTO))
async def object_load_photo(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    paths = []
    tokens = []
    for attachment in message.message.body.attachments:
        if attachment.type in ("image", "video") and len(paths) < 5:
            path = await utils.download(attachment, USERS_FILES_FOLDER_PATH)
            if path != "api error":
                paths.append(path)
                tokens.append(attachment.payload.token)
            else:
                pass # todo обработчик ошибок (если api макса не отвечает код 200)
    await fsm_context.update_data(photos=tokens)
    await fsm_context.set_state(OBJECT_LOAD_DOCUMENTS)
    await message.answer("Загрузите ссылку на документы (например Яндекс диск)", keyboard=cancel_object_creation_kb())

# Создание объекта: ввод документов
@router.message_created(StateFilter(OBJECT_LOAD_DOCUMENTS))
async def object_load_documents(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("documents_link", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(documents=value)
    await fsm_context.set_state(OBJECT_SET_PRICE)
    await message.answer("введите цену", keyboard=cancel_object_creation_kb())

# Создание объекта: ввод стоимости
@router.message_created(StateFilter(OBJECT_SET_PRICE))
async def object_set_price(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    if not message.text.isdigit():
        await message.answer("введи циферки, Тёмочка")
        return

    await fsm_context.update_data(price=float(message.text))
    await fsm_context.set_state(OBJECT_CONFIRM)
    data = await fsm_context.get_data()
    photo_requests = []
    for i in data["photos"]:
        photo_requests.append(
            PhotoAttachmentRequest(
                payload=PhotoAttachmentRequestPayload(token=i)
            )
        )
    await message.answer(text=f"""Подтвердите создание объекта:
Город: {data["city"]}
Адрес: {data["address"]}
Описание: {data["description"]}
документы: {data["documents"]}
Цена: {data["price"]}
ниже приведены фото и документы
""", attachments=photo_requests, keyboard=confirm_object_creation_kb())

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

    elif payload == "menu:objects":
        user_places = await db.get_user_places(user.id, session)
        if user_places == "Error":
            pass # todo хэндлер ошибки
        elif len(user_places) != 0:
            await fsm_context.clear()
            await cb.edit_message(
                text=f"Ваши объекты ({len(user_places)}/{MAX_OBJECTS})",
                keyboard=my_objects_kb(user_places, len(user_places) < MAX_OBJECTS),
            )
        else:
            await fsm_context.clear()
            await fsm_context.set_state(NO_CREATED_OBJECTS)
            await cb.edit_message(text=NO_CREATED_OBJECTS_TEXT, keyboard=no_created_objects_kb())

    elif payload == "menu:change": # смотреть объекты: выбор города
        await fsm_context.clear()
        await cb.edit_message(text="Выберите город:", keyboard=cities_kb())

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

    elif payload.startswith("object:"): # обработка приколов про объекты
        field = payload.split(":", 1)[1]
        if field == "new":
            if len(await db.get_user_places(user.id, session)) >= MAX_OBJECTS:
                await cb.callback_answer(notification=f"Можно создать не больше {MAX_OBJECTS} объектов")
                return
            await fsm_context.set_state(OBJECT_SET_CITY)
            await cb.edit_message(text="Введите город", keyboard=cities_kb())
        if field == "confirm":
            data = await fsm_context.get_data()
            await db.create_place(
                Place(
                    user = user,
                    city = data["city"],
                    address = data["address"],
                    cost = data["price"],
                    description = data["description"],
                    photo = ",".join(data["photos"]),
                    url_documents = data["documents"],
                    creation_date = datetime.now(timezone.utc)
                ), session
            )
            await fsm_context.clear()
            await cb.edit_message(text=f"Объект создан\n\n{MAIN_MENU_TEXT}", keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)
        if field.isdigit(): # карточка объекта, payload = object:{id}
            place = await db.get_place_by_id(int(field), session)
            if not place:
                await cb.callback_answer(notification=OUTDATED)
                return
            owner = await db.get_user_by_id(place.user_id, session)
            photos = [PhotoAttachmentRequest(payload=PhotoAttachmentRequestPayload(token=t)) for t in place.photo.split(",") if t]
            await fsm_context.update_data(place=place)
            await cb.edit_message(text=f"""Адрес: {place.address}
Цена: {int(place.cost)} ₽
Описание: {place.description}
Документы: {place.url_documents}

Владелец: {owner.name}
Телефон: {owner.phone_number}""", attachments=photos, keyboard=place_kb())
        if field == "delete":
            place = await fsm_context.get_value("place")
            await db.delete_place(place, session)
            await fsm_context.clear()
            await cb.edit_message(text=MAIN_MENU_TEXT, keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)

    elif payload.startswith("city:"): # city:{city} или city:{city}:{page}
        parts = payload.split(":")
        city = parts[1] # города на английском языке
        if await fsm_context.get_state() == OBJECT_SET_CITY:
            await fsm_context.update_data(city=city)
            await fsm_context.set_state(OBJECT_SET_ADDRESS)
            await cb.edit_message(text="Введите адрес", keyboard=cancel_object_creation_kb())
        else: # просмотр объектов города
            page = int(parts[2]) if len(parts) == 3 else 0
            places = await db.get_city_places(city, session)
            if not places:
                await cb.callback_answer(notification="В этом городе пока нет объектов")
                return
            pages_count = (len(places) + PAGE_SIZE - 1) // PAGE_SIZE
            page_places = places[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            await cb.edit_message(
                text=f"Объекты (стр. {page + 1}/{pages_count})",
                keyboard=city_objects_kb(page_places, city, page, pages_count),
            )

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