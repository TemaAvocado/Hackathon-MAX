from maxo.utils.builders import KeyboardBuilder

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