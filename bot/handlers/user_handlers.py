import re
from datetime import datetime, timezone
from pathlib import Path

from maxo import Router
from maxo.fsm import FSMContext, StateFilter
from maxo.routing.filters import Command, CommandStart
from maxo.types import BotStarted, MessageCallback, MessageCreated, PhotoAttachmentRequest, PhotoAttachmentRequestPayload
from maxo.enums import TextFormat
from maxo.utils.upload_media import BufferedInputFile

from ..states.user_states import REG_NAME, REG_PHONE, REG_CITY, EDIT, NO_CREATED_OBJECTS, OBJECT_SET_CITY, OBJECT_SET_ADDRESS, OBJECT_SET_DESCRIPTION, OBJECT_LOAD_PHOTO, OBJECT_LOAD_DOCUMENTS, OBJECT_SET_PRICE, OBJECT_CONFIRM, SEARCH_ID, SEARCH_QR
from ..keyboards.user_keyboards import main_menu_kb, profile_kb, cancel_edit_kb, no_created_objects_kb, cities_kb, cancel_object_creation_kb, confirm_object_creation_kb, city_objects_kb, my_objects_kb, place_kb, app_cities_kb, quick_search_kb, cancel_search_kb, no_city_places_kb, favorites_kb, back_to_menu_kb
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
MAX_OBJECTS = 5

# Экраны, на которые может вести кнопка Назад из карточки объекта
BACK_PAYLOAD_RE = re.compile(r"^(menu:(main|objects|favorites)|search:menu|city:[A-Za-z]+:\d+)$")

NO_CREATED_OBJECTS_TEXT = """**Вы пока не размещали объекты для сдачи в аренду.**

_Нажмите **'Создать новый'**, что бы разместить ваш объект на площадке._"""

HELP_TEXT = """💬 **Помощь**

Если вы столкнулись с проблемами при использовании бота, есть предложения по улучшению или хотите задать вопрос - перейдите в [Чат с администратором бота](https://max.ru/u/f9LHodD0cOLd88ifVqUZbaj43lejAs-8iQqrotKhhjO1Zp87rSV-NIF2dCI)"""

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
        
⚠️ _**Важно:** вводите актуальные данные, они будут предоставлены для связи с арендодателем/арендатором._''')


def safe_back(back: str | None) -> str:
    return back if back and BACK_PAYLOAD_RE.match(back) else "menu:main"


async def my_objects_screen(user: User, fsm_context: FSMContext, session: SessionDep):
    await fsm_context.clear()
    user_places = await db.get_user_places(user.id, session)
    if user_places == "Error" or not user_places:
        await fsm_context.set_state(NO_CREATED_OBJECTS)
        return NO_CREATED_OBJECTS_TEXT, no_created_objects_kb()
    return (
        f"Ваши объекты, размещенные в данный момент на площадке. ({len(user_places)}/{MAX_OBJECTS})",
        my_objects_kb(user_places, len(user_places) < MAX_OBJECTS),
    )


async def favorites_screen(user: User, session: SessionDep):
    saved_places = await db.get_user_saved_places(user.id, session)
    if saved_places == "Error" or not saved_places:
        return "Здесь появятся объекты, которые вы добавите в избранное.", back_to_menu_kb()
    return f"❤️ Избранное ({len(saved_places)})", favorites_kb(saved_places)


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


# /objects: мои объекты
@router.message_created(Command("objects"))
async def on_objects(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    user = await db.get_user_by_id(message.user_id, session)
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    text, keyboard = await my_objects_screen(user, fsm_context, session)
    await message.answer(text=text, keyboard=keyboard, format=TextFormat.MARKDOWN)


# /favorites: избранное
@router.message_created(Command("favorites"))
async def on_favorites(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    user = await db.get_user_by_id(message.user_id, session)
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    await fsm_context.clear()
    text, keyboard = await favorites_screen(user, session)
    await message.answer(text=text, keyboard=keyboard)


# Заглушка нижнего меню
@router.message_created(Command("map"))
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
    await message.answer(text=f"✅ **Регистрация завершена**\n\n{MAIN_MENU_TEXT}", keyboard=main_menu_kb(), format=TextFormat.MARKDOWN)

# Создание объекта: ввод адреса
@router.message_created(StateFilter(OBJECT_SET_ADDRESS))
async def object_set_address(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("address", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(address=value)
    await fsm_context.set_state(OBJECT_SET_DESCRIPTION)
    await message.answer("""**Добавьте описание к карточке вашего объекта.**
    
_Совет: аудитория площадки — представители бизнеса. Делайте акцент на коммерческой выгоде, цифрах, площади, логистике и других ключевых параметрах. Все второстепенные нюансы можно будет обсудить с клиентом в переписке_""", keyboard=cancel_object_creation_kb(), format=TextFormat.MARKDOWN)

# Создание объекта: ввод описания
@router.message_created(StateFilter(OBJECT_SET_DESCRIPTION))
async def object_set_description(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("description", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(description=value)
    await fsm_context.set_state(OBJECT_LOAD_PHOTO)
    await message.answer("Загрузите фотографии объекта, бот может принять максимум 5 изображений.", keyboard=cancel_object_creation_kb())

# Создание объекта: ввод фото
@router.message_created(StateFilter(OBJECT_LOAD_PHOTO))
async def object_load_photo(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    paths = []
    tokens = []
    for attachment in message.message.body.attachments or []: # вложений может не быть совсем
        if attachment.type in ("image", "video") and len(paths) < 5:
            path = await utils.download(attachment, USERS_FILES_FOLDER_PATH)
            if path != "api error":
                paths.append(path)
                tokens.append(attachment.payload.token)
            else:
                pass 
    await fsm_context.update_data(photos=tokens)
    await fsm_context.set_state(OBJECT_LOAD_DOCUMENTS)
    await message.answer("""**При необходимости прикрепите ссылку на облако с документами. Если её нет, введите "-".**
    
_Совет: в облако можно загрузить планировку объекта, расширенные требования города/администрации/округа, ограничения или расширенное описание объекта._""", keyboard=cancel_object_creation_kb(), format=TextFormat.MARKDOWN)

# Создание объекта: ввод документов
@router.message_created(StateFilter(OBJECT_LOAD_DOCUMENTS))
async def object_load_documents(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    value, error = parsers.parse_field("documents_link", message.text)
    if not value:
        await message.answer(error)
        return
    await fsm_context.update_data(documents=value)
    await fsm_context.set_state(OBJECT_SET_PRICE)
    await message.answer("""Введите ежемесячную плату за аренду помещения.
    
_Пример: 75000, 100000._""", keyboard=cancel_object_creation_kb(), format=TextFormat.MARKDOWN)

# Создание объекта: ввод стоимости
@router.message_created(StateFilter(OBJECT_SET_PRICE))
async def object_set_price(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    text = (message.text or "").strip() # текста может не быть (прислали фото/стикер)
    if not text.isdigit():
        await message.answer("Введите целое число")
        return

    await fsm_context.update_data(price=float(text))
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

Ссылка на облако с документами: {data["documents"]}

Цена: {data["price"]} ₽/мес.""", attachments=photo_requests, keyboard=confirm_object_creation_kb())

# Быстрый поиск: ввод ID
@router.message_created(StateFilter(SEARCH_ID))
async def search_by_id(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    place_id = (message.text or "").strip().split(":")[-1] # принимаем и 15, и object:15
    if not place_id.isdigit():
        await message.answer("Введите ID объекта, который хотите найти, его можно узнать у владельца карточки объекта.", keyboard=cancel_search_kb())
        return
    await send_found_place(message, int(place_id), fsm_context, session)

# Быстрый поиск: фото QR-кода (в QR лежит id объекта или object:{id})
@router.message_created(StateFilter(SEARCH_QR))
async def search_by_qr(message: MessageCreated, fsm_context: FSMContext, session: SessionDep) -> None:
    images = [a for a in (message.message.body.attachments or []) if a.type == "image"]
    if not images:
        await message.answer("Отправьте фото QR-кода объекта, который хотите найти, его можно узнать у владельца карточки объекта.", keyboard=cancel_search_kb())
        return
    path = await utils.download(images[0], USERS_FILES_FOLDER_PATH)
    if path == "api error":
        await message.answer("Не удалось загрузить фото, попробуйте ещё раз.", keyboard=cancel_search_kb())
        return
    place_id = utils.read_qr(path).split(":")[-1]
    path.unlink() # фото QR больше не нужно
    if not place_id.isdigit():
        await message.answer("QR-код не распознан, попробуйте ещё раз.", keyboard=cancel_search_kb())
        return
    await send_found_place(message, int(place_id), fsm_context, session)

# Все нажатия кнопок.
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
        text, keyboard = await my_objects_screen(user, fsm_context, session)
        await cb.edit_message(text=text, keyboard=keyboard, format=TextFormat.MARKDOWN)

    elif payload == "menu:help":
        await fsm_context.clear()
        await cb.edit_message(text=HELP_TEXT, keyboard=back_to_menu_kb(), format=TextFormat.MARKDOWN)

    elif payload == "menu:favorites":
        await fsm_context.clear()
        text, keyboard = await favorites_screen(user, session)
        await cb.edit_message(text=text, keyboard=keyboard)

    elif payload.startswith("fav:"): 
        parts = payload.split(":", 3)
        if len(parts) < 3 or parts[1] not in ("add", "remove") or not parts[2].isdigit():
            await cb.callback_answer(notification=OUTDATED)
            return
        action, place_id = parts[1], int(parts[2])
        back = safe_back(parts[3] if len(parts) == 4 else None)
        place = await db.get_place_by_id(place_id, session)
        if not place:
            await cb.callback_answer(notification=OUTDATED)
            return
        if action == "add":
            if place.user_id == user.id:
                await cb.callback_answer(notification="Свои объекты нельзя добавить в избранное")
                return
            if await db.add_saved_place(user.id, place_id, session) == "Error":
                await cb.callback_answer(notification="Объект уже в избранном.")
                return
            notification = "Добавлено в избранное"
        else:
            if await db.remove_saved_place(user.id, place_id, session) == "Error":
                await cb.callback_answer(notification="Объекта уже нет в избранном.")
                return
            notification = "Убрано из избранного"
        await show_place_card(cb, place, user.id, session, back)
        await cb.callback_answer(notification=notification)

    elif payload.startswith("qr:"): 
        place_id = payload.split(":", 1)[1]
        place = await db.get_place_by_id(int(place_id), session) if place_id.isdigit() else None
        if not place:
            await cb.callback_answer(notification=OUTDATED)
            return
        if place.user_id != user.id:
            await cb.callback_answer(notification="QR-код можно создать только для своего объекта.")
            return
        qr_image = utils.make_qr(f"object:{place.id}")
        await cb.send_message(
            text=f"""QR-код объекта ID {place.id}.
Адрес: {place.address}.

Его можно отсканировать в разделе «Смотреть объекты → Быстрый поиск → Сканировать QR-код»""",
            media=[BufferedInputFile.image(qr_image, f"qr_{place.id}.png")],
        )
        await cb.callback_answer(notification="QR-код отправлен")

    elif payload == "menu:change": 
        await fsm_context.clear()
        await cb.edit_message(text="Выберите город, в котором хотите арендовать помещение:", keyboard=app_cities_kb())

    elif payload == "search:menu":
        await fsm_context.clear()
        await cb.edit_message(text="🔍 Быстрый поиск", keyboard=quick_search_kb())

    elif payload == "search:id":
        await fsm_context.set_state(SEARCH_ID)
        await cb.edit_message(text="Введите ID объекта:", keyboard=cancel_search_kb())

    elif payload == "search:qr":
        await fsm_context.set_state(SEARCH_QR)
        await cb.edit_message(text="Отправьте фото QR-кода объекта:", keyboard=cancel_search_kb())

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

    elif payload.startswith("object:"): 
        parts = payload.split(":", 2)
        field = parts[1] if len(parts) > 1 else ""

        if field == "new":
            if len(await db.get_user_places(user.id, session)) >= MAX_OBJECTS:
                await cb.callback_answer(notification=f"Можно создать не больше {MAX_OBJECTS} объектов")
                return
            await fsm_context.set_state(OBJECT_SET_CITY)
            await cb.edit_message(text="Укажите город, в котором находится помещение.", keyboard=cities_kb())

        elif field == "confirm":
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

        elif field == "delete": 
            place_id = parts[2] if len(parts) == 3 else ""
            place = await db.get_place_by_id(int(place_id), session) if place_id.isdigit() else None
            if not place:
                await cb.callback_answer(notification=OUTDATED)
                return
            if place.user_id != user.id:
                await cb.callback_answer(notification="Удалить можно только свой объект")
                return
            await db.delete_place(place.id, session)
            text, keyboard = await my_objects_screen(user, fsm_context, session)
            await cb.edit_message(text=text, keyboard=keyboard, format=TextFormat.MARKDOWN)
            await cb.callback_answer(notification="Объект удалён")

        elif field.isdigit(): 
            place = await db.get_place_by_id(int(field), session)
            if not place:
                await cb.callback_answer(notification=OUTDATED)
                return
            back = safe_back(parts[2] if len(parts) == 3 else None)
            await show_place_card(cb, place, user.id, session, back)

        else:
            await cb.callback_answer(notification=OUTDATED)

    elif payload.startswith("city:"): 
        parts = payload.split(":")
        city = parts[1] 
        if await fsm_context.get_state() == OBJECT_SET_CITY:
            await fsm_context.update_data(city=city)
            await fsm_context.set_state(OBJECT_SET_ADDRESS)
            await cb.edit_message(text="Введите адрес объекта, который будете сдавать в аренду.", keyboard=cancel_object_creation_kb())
        else: 
            page = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else 0
            places = await db.get_city_places(city, session)
            if not places:
                await cb.edit_message(text="В этом городе пока нет объектов, сдающихся в аренду.", keyboard=no_city_places_kb())
                return
            pages_count = (len(places) + PAGE_SIZE - 1) // PAGE_SIZE
            page = min(page, pages_count - 1) 
            page_places = places[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
            await cb.edit_message(
                text=f"Объекты для аренды, в выбранном городе. (стр. {page + 1}/{pages_count})",
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

    user = await db.get_user_by_id(message.user_id, session)
    await message.answer(text=f"**Сохранено**\n\n{profile_text(user)}", keyboard=profile_kb(), format=TextFormat.MARKDOWN)


# Любое другое сообщение
@router.message_created()
async def unknown_message(message: MessageCreated, session: SessionDep) -> None:
    user = await db.get_user_by_id(message.user_id, session)
    if not user:
        await message.answer(NOT_REGISTERED)
        return
    await message.answer(text="Воспользуйтесь меню", keyboard=main_menu_kb())

# Текст и фото карточки объекта
async def place_card(place: Place, session: SessionDep):
    owner = await db.get_user_by_id(place.user_id, session)
    photos = [PhotoAttachmentRequest(payload=PhotoAttachmentRequestPayload(token=t)) for t in place.photo.split(",") if t]
    text = f"""ID: {place.id}

Адрес: {place.address}

Цена аренды: {int(place.cost)} ₽/мес.

Описание: {place.description}

Ссылка на облако с документами: {place.url_documents}

Владелец: {owner.name}
Контакт владельца: {owner.phone_number}"""
    return text, photos

# Показать карточку объекта в текущем сообщении (кнопки зависят от владельца, избранного и того, откуда пришли)
async def show_place_card(cb: MessageCallback, place: Place, user_id: int, session: SessionDep, back: str = "menu:main") -> None:
    text, photos = await place_card(place, session)
    is_owner = place.user_id == user_id
    is_saved = not is_owner and await db.is_place_saved(user_id, place.id, session)
    await cb.edit_message(text=text, attachments=photos, keyboard=place_kb(place.id, is_owner, is_saved, back))

# Быстрый поиск: отправить карточку найденного объекта
async def send_found_place(message: MessageCreated, place_id: int, fsm_context: FSMContext, session: SessionDep) -> None:
    place = await db.get_place_by_id(place_id, session)
    if not place:
        await message.answer("Объект не найден, попробуйте ещё раз.", keyboard=cancel_search_kb())
        return
    await fsm_context.clear()
    text, photos = await place_card(place, session)
    is_owner = place.user_id == message.user_id
    is_saved = not is_owner and await db.is_place_saved(message.user_id, place.id, session)
    await message.answer(text=text, attachments=photos, keyboard=place_kb(place.id, is_owner, is_saved, "search:menu"))