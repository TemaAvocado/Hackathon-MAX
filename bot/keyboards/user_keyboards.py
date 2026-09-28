from maxo.utils.builders import KeyboardBuilder


# Клавиатура главного меню
def main_menu_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="🔎 Смотреть объекты", payload="menu:change")
        .add_callback(text="👤 Профиль", payload="menu:profile")
        .add_callback(text="🏢 Мои объекты", payload="menu:objects")
        .add_callback(text="❤️ Избранное", payload="menu:favorites")
        .add_callback(text="💬 Помощь", payload="menu:help")
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


# Кнопка отмены при редактировании поля профиля
def cancel_edit_kb(): # todo мб стоит переименовать чтобы подчеркнуть что это именно для редактирования профиля
    return (
        KeyboardBuilder()
        .add_callback(text="Отмена", payload="menu:profile")
        .build()
    )

# Кнопка отмены при создании объекта
def cancel_object_creation_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="Отмена", payload="menu:objects")
        .build()
    )

# Клавиатура экрана объектов если у пользователя нет объектов
def no_created_objects_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="Создать новый", payload="object:new")
        .add_callback(text="Назад", payload="menu:main")
        .build()
    )

def confirm_object_creation_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="Подтвердить", payload="object:confirm")
        .add_callback(text="Отмена", payload="menu:objects")
        .build()
    )

# Клавиатура выбора города (по идее можно использовать не только для создания объекта)
def cities_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="Москва", payload="city:moscow")
        .add_callback(text="Санкт-Петербург", payload="city:SPetersburg")
        .add_callback(text="Екатеринбург", payload="city:Yekaterinburg")
        .add_callback(text="Новосибирск", payload="city:Novosibirsk")
        .add_callback(text="Калининград", payload="city:Kaliningrad")
        .add_callback(text="Казань", payload="city:Kazan")
        .add_callback(text="Краснодар", payload="city:Krasnodar")
        .add_callback(text="Отмена", payload="menu:main")
        .adjust(1)
        .build()
    )

# Клавиатура карточки объекта
def place_kb():
    return (
        KeyboardBuilder()
        .add_callback(text="В меню", payload="menu:main")
        .build()
    )

# Клавиатура объектов города: по кнопке на объект + вперед/назад
def city_objects_kb(places, city, page, pages_count):
    kb = KeyboardBuilder()
    for place in places:
        kb.add_callback(text=f"{place.address} — {int(place.cost)} ₽", payload=f"object:{place.id}")
    kb.adjust(1)

    nav = KeyboardBuilder()
    if page > 0:
        nav.add_callback(text="⬅️ Назад", payload=f"city:{city}:{page - 1}")
    if page < pages_count - 1:
        nav.add_callback(text="Вперед ➡️", payload=f"city:{city}:{page + 1}")
    kb.attach(nav)

    kb.attach(KeyboardBuilder().add_callback(text="К городам", payload="menu:change"))
    return kb.build()

# Клавиатура моих объектов
def my_objects_kb(places, can_create):
    kb = KeyboardBuilder()
    for place in places:
        kb.add_callback(text=f"{place.address} — {int(place.cost)} ₽", payload=f"object:{place.id}")
    if can_create:
        kb.add_callback(text="Создать новый", payload="object:new")
    kb.add_callback(text="В меню", payload="menu:main")
    return kb.adjust(1).build()
