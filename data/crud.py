from sqlalchemy import select

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

    result = await session.execute(select(Place).where(SavedObject.user_id == id))
    return result.scalars().all()

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
