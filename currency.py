"""Получение, кэширование и конвертация курсов валют."""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import requests


FAVORITE_CURRENCIES = ["USD", "EUR", "GBP", "RUB"]
DISPLAY_CURRENCIES = ["RUB", "EUR", "GBP"]
DEFAULT_CACHE_PATH = "currency_rate.json"
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT = 15
DEFAULT_BASE_CURRENCY = "RUB"


class CurrencyError(Exception):
    """Понятная пользователю ошибка получения или обработки курсов."""


def normalize_currency_code(currency_code: str) -> str:
    """Привести код валюты к формату ISO 4217 и проверить его вид."""
    normalized_code = currency_code.strip().upper()
    if len(normalized_code) != 3 or not normalized_code.isalpha():
        raise CurrencyError("Код валюты должен состоять из трёх букв, например USD.")
    return normalized_code


def get_currency_rates(base: str) -> dict[str, Any]:
    """Получить с сервера таблицу курсов для базовой валюты."""
    base_code = normalize_currency_code(base)
    url = f"https://open.er-api.com/v6/latest/{base_code}"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as error:
        raise CurrencyError(
            "Не удалось подключиться к сервису курсов. "
            "Проверьте интернет-соединение и повторите попытку."
        ) from error

    if response.status_code != 200:
        raise CurrencyError(
            "Сервис курсов вернул ошибку "
            f"(HTTP {response.status_code}). Попробуйте повторить запрос позже."
        )

    try:
        data = response.json()
    except (requests.exceptions.JSONDecodeError, ValueError) as error:
        raise CurrencyError("Сервис курсов вернул некорректный JSON.") from error

    if not isinstance(data, dict):
        raise CurrencyError("Сервис курсов вернул данные неожиданного формата.")

    if data.get("result") != "success":
        error_type = data.get("error-type", "неизвестная ошибка")
        raise CurrencyError(f"Сервис не смог получить курс: {error_type}.")

    _get_rates(data)
    return data


def save_to_file(
    data: dict[str, Any], path: str | Path = DEFAULT_CACHE_PATH
) -> None:
    """Сохранить данные в JSON-файл в кодировке UTF-8."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def read_from_file(path: str | Path = DEFAULT_CACHE_PATH) -> dict[str, Any]:
    """Прочитать словарь с курсами из JSON-файла."""
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise CurrencyError("Файл кэша содержит данные неожиданного формата.")
    return data


def _get_rates(data: dict[str, Any]) -> dict[str, float]:
    """Вернуть таблицу курсов из открытого или стандартного формата API."""
    rates = data.get("rates")
    if rates is None:
        rates = data.get("conversion_rates")

    if not isinstance(rates, dict) or not rates:
        raise CurrencyError("В полученных данных отсутствует таблица курсов.")
    return rates


def is_cache_fresh(
    path: str | Path = DEFAULT_CACHE_PATH,
    max_age_seconds: int = CACHE_MAX_AGE_SECONDS,
) -> bool:
    """Проверить, что файл кэша существует и создан менее суток назад."""
    cache_path = Path(path)
    try:
        age_seconds = time.time() - cache_path.stat().st_mtime
    except OSError:
        return False
    return age_seconds < max_age_seconds


def update_currency_rates(
    base: str, path: str | Path = DEFAULT_CACHE_PATH
) -> dict[str, Any]:
    """Загрузить свежие курсы и обновить файл кэша."""
    data = get_currency_rates(base)
    try:
        save_to_file(data, path)
    except OSError as error:
        raise CurrencyError(f"Не удалось сохранить файл кэша: {error}") from error
    return data


def load_currency_rates(
    base: str, path: str | Path = DEFAULT_CACHE_PATH
) -> tuple[dict[str, Any], bool]:
    """Прочитать свежий кэш либо запросить и сохранить новые данные."""
    base_code = normalize_currency_code(base)
    if is_cache_fresh(path):
        try:
            cached_data = read_from_file(path)
            cached_rates = _get_rates(cached_data)
        except (OSError, json.JSONDecodeError, CurrencyError):
            print("Кэш повреждён или имеет неверный формат. Получаю свежие данные.")
        else:
            if base_code not in cached_rates:
                raise CurrencyError(
                    f"Валюта {base_code} отсутствует в списке доступных кодов."
                )
            return cached_data, True

    return update_currency_rates(base_code, path), False


def available_currency_codes(data: dict[str, Any]) -> list[str]:
    """Вернуть коды валют в порядке ответа API (базовая валюта — первая)."""
    return list(_get_rates(data))


def convert_currency(
    data: dict[str, Any], from_currency: str, to_currency: str, amount: float
) -> float:
    """Конвертировать сумму между любыми двумя валютами из таблицы."""
    source_code = normalize_currency_code(from_currency)
    target_code = normalize_currency_code(to_currency)
    rates = _get_rates(data)

    missing_codes = [code for code in (source_code, target_code) if code not in rates]
    if missing_codes:
        raise CurrencyError(
            f"Валюта {', '.join(missing_codes)} недоступна. "
            "Посмотрите список доступных кодов в меню."
        )

    if not math.isfinite(amount) or amount < 0:
        raise CurrencyError("Сумма должна быть неотрицательным конечным числом.")

    try:
        source_rate = float(rates[source_code])
        target_rate = float(rates[target_code])
    except (TypeError, ValueError) as error:
        raise CurrencyError("Таблица содержит некорректное значение курса.") from error
    if source_rate == 0:
        raise CurrencyError(f"Для валюты {source_code} получен нулевой курс.")
    return amount * target_rate / source_rate


def print_favorite_rates(data: dict[str, Any], base: str) -> None:
    """Вывести курсы RUB, EUR и GBP относительно выбранной валюты."""
    base_code = normalize_currency_code(base)
    print(f"\nКурсы для 1 {base_code}:")
    for target_code in DISPLAY_CURRENCIES:
        try:
            rate = convert_currency(data, base_code, target_code, 1)
        except CurrencyError:
            print(f"  {target_code}: нет данных")
        else:
            print(f"  {target_code}: {rate:.4f}")


def read_amount() -> float:
    """Прочитать из консоли сумму, разрешая запятую как разделитель."""
    raw_amount = input("Сумма: ").strip().replace(",", ".")
    try:
        return float(raw_amount)
    except ValueError as error:
        raise CurrencyError("Сумма должна быть числом, например 100 или 12.50.") from error


def run_converter(data: dict[str, Any]) -> None:
    """Запросить параметры и вывести результат конвертации."""
    amount = read_amount()
    print("\nДоступные валюты: " + ", ".join(available_currency_codes(data)))
    source_code = input(
        "Введите исходную валюту (например, USD): "
    ).strip()
    target_code = input(
        "Введите целевую валюту (например, EUR): "
    ).strip()
    result = convert_currency(data, source_code, target_code, amount)
    print(
        f"\n{amount} {source_code.upper()} = "
        f"{result:.2f} {target_code.upper()}"
    )


def print_currency_info(data: dict[str, Any], currency_code: str) -> None:
    """Вывести курс и время обновления для выбранной валюты."""
    code = normalize_currency_code(currency_code)
    rates = _get_rates(data)
    if code not in rates:
        raise CurrencyError(
            f"Валюта {code} недоступна. Посмотрите список кодов в меню."
        )

    base_code = normalize_currency_code(
        str(data.get("base_code", DEFAULT_BASE_CURRENCY))
    )
    direct_rate = convert_currency(data, base_code, code, 1)
    reverse_rate = convert_currency(data, code, base_code, 1)

    print(f"\nИнформация о валюте {code}")
    print(f"1 {base_code} = {direct_rate:.4f} {code}")
    print(f"1 {code} = {reverse_rate:.4f} {base_code}")
    print(
        "Последнее обновление: "
        f"{data.get('time_last_update_utc', 'нет данных')}"
    )
    print(
        "Следующее обновление: "
        f"{data.get('time_next_update_utc', 'нет данных')}"
    )


def print_menu() -> None:
    """Показать главное меню конвертера."""
    print("\n=== Конвертер валют ===")
    print("1. Конвертировать валюту")
    print("2. Показать доступные валюты")
    print("3. Информация о конкретной валюте")
    print("4. Обновить курсы валют")
    print("5. Выход")


def wait_for_enter() -> None:
    """Оставить результат на экране до подтверждения пользователя."""
    input("\nНажмите Enter для продолжения...")


def configure_console() -> None:
    """Включить UTF-8 для корректного вывода в Windows-консоли."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    """Запустить интерактивный справочник и конвертер валют."""
    configure_console()

    try:
        data, _ = load_currency_rates(DEFAULT_BASE_CURRENCY)
    except CurrencyError as error:
        print(f"Ошибка: {error}")
        return

    while True:
        print_menu()
        choice = input("\nВыберите действие (1-5): ").strip()

        try:
            if choice == "1":
                run_converter(data)
            elif choice == "2":
                print(
                    "\nДоступные валюты: "
                    + ", ".join(available_currency_codes(data))
                )
            elif choice == "3":
                currency_code = input("Введите код валюты: ").strip()
                print_currency_info(data, currency_code)
            elif choice == "4":
                current_base = str(
                    data.get("base_code", DEFAULT_BASE_CURRENCY)
                ).upper()
                update_base = input(
                    f"Введите базовую валюту [{current_base}]: "
                ).strip() or current_base
                data = update_currency_rates(update_base)
                print("Данные обновлены в currency_rate.json.")
            elif choice == "5":
                print("До свидания!")
                break
            else:
                print("Введите номер от 1 до 5.")
                continue
        except CurrencyError as error:
            print(f"Ошибка: {error}")

        wait_for_enter()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nРабота программы завершена.")
