import re

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