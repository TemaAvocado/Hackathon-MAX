from sqlalchemy import select, delete

from data.models import User, Place, SavedObject
from utils.parsers import normalize_phone
from data import SessionDep


# Проверяем, существует ли объект
async def exists(obj) -> bool:
    return obj is not None

# Выбор пользователя по id
async def get_user_by_id(id: int, session: SessionDep) -> User | None:
    return await session.get(User, id)

# Изменить имя пользователя
async def set_user_name(id: int, name: str, session: SessionDep):
    user = await get_user_by_id(id, session)
    if not await exists(user):
        return "Error"

    name = name.strip()
    if not name:
        return "Error"

    user.name = name
    await session.commit()
    await session.refresh(user)
    return None

# Изменить номер пользователя
async def set_user_phone(id: int, phone: str, session: SessionDep):
    user = await get_user_by_id(id, session)
    if not await exists(user):
        return "Error"

    normalized = normalize_phone(phone)
    if normalized is None:
        return "Error"

    user.phone_number = normalized
    await session.commit()
    await session.refresh(user)
    return None

# Изменить город пользователя
async def set_user_city(id: int, city: str, session: SessionDep):
    user = await get_user_by_id(id, session)
    if not await exists(user):
        return "Error"

    city = city.strip()
    if not city:
        return "Error"

    user.city = city
    await session.commit()
    await session.refresh(user)
    return None

# Получить все места из избранного пользователя
async def get_user_saved_places(id: int, session: SessionDep):
    if not await exists(await get_user_by_id(id, session)):
        return "Error"

    result = await session.execute(
        select(Place)
        .join(SavedObject, SavedObject.object_id == Place.id)
        .where(SavedObject.user_id == id)
        .order_by(SavedObject.id)
    )
    return result.scalars().all()

# Запись избранного пользователя по объекту
async def get_saved_object(user_id: int, place_id: int, session: SessionDep) -> SavedObject | None:
    result = await session.execute(
        select(SavedObject).where(SavedObject.user_id == user_id, SavedObject.object_id == place_id)
    )
    return result.scalars().first()

# Объект в избранном у пользователя - проверка
async def is_place_saved(user_id: int, place_id: int, session: SessionDep) -> bool:
    return await exists(await get_saved_object(user_id, place_id, session))

# Добавить объект в избранное
async def add_saved_place(user_id: int, place_id: int, session: SessionDep):
    if await is_place_saved(user_id, place_id, session):
        return "Error"

    session.add(SavedObject(user_id=user_id, object_id=place_id))
    await session.commit()
    return None

# Убрать объект из избранного
async def remove_saved_place(user_id: int, place_id: int, session: SessionDep):
    saved = await get_saved_object(user_id, place_id, session)
    if not await exists(saved):
        return "Error"

    await session.delete(saved)
    await session.commit()
    return None

# Получить все объекты пользователя
async def get_user_places(id: int, session: SessionDep):
    if not await exists(await get_user_by_id(id, session)):
        return "Error"

    result = await session.execute(select(Place).where(Place.user_id == id))
    return result.scalars().all()

# Добавить пользователя
async def create_user(user: User, session: SessionDep): 
    if await exists(await get_user_by_id(user.id, session)):
        return "Error"
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return None

# Извлечь все адреса
async def get_all_addresses(session: SessionDep):
    result = await session.execute(select(Place.address))
    return result.scalars()

# Выбор объекта по id
async def get_place_by_id(id: int, session: SessionDep) -> Place | None:
    return await session.get(Place, id)

# Добавить объект
async def create_place(place: Place, session: SessionDep):
    if await exists(await get_place_by_id(place.id, session)):
        return "Error"

    session.add(place)
    await session.commit()
    await session.refresh(place)
    return None

# Получить все объекты города
async def get_city_places(city: str, session: SessionDep):
    result = await session.execute(select(Place).where(Place.city == city))
    return result.scalars().all()

# Удалить объект (сначала убираем его из избранного у всех, иначе не даст внешний ключ)
async def delete_place(place_id: int, session: SessionDep):
    place = await get_place_by_id(place_id, session)
    if not await exists(place):
        return "Error"

    await session.execute(delete(SavedObject).where(SavedObject.object_id == place_id))
    await session.delete(place)
    await session.commit()
    return None