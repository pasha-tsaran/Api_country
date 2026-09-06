"""Красивый вывод информации о странах из REST Countries API."""

from __future__ import annotations

import sys
from typing import Any

import requests
from colorama import Fore, Style, init


API_URL = "https://restcountries.com/v3.1/name/{country}"
DATASET_URL = (
    "https://raw.githubusercontent.com/restcountries/restcountries/"
    "master/src/main/resources/countriesV3.1.json"
)
REQUEST_TIMEOUT = 15


def configure_console() -> None:
    """Включить UTF-8 для цветов и специальных символов в Windows-консоли."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def format_mapping_values(items: dict[str, Any]) -> str:
    """Объединить отображаемые значения словаря через запятую."""
    return ", ".join(str(value) for value in items.values()) or "Нет данных"


def format_currencies(currencies: dict[str, dict[str, str]]) -> str:
    """Подготовить названия, коды и символы валют для вывода."""
    result = []
    for code, details in currencies.items():
        name = details.get("name", "Неизвестно")
        symbol = details.get("symbol")
        result.append(f"{name} ({code}{f', символ: {symbol}' if symbol else ''})")
    return ", ".join(result) or "Нет данных"


def find_country(countries: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    """Найти страну по английскому названию в списке записей."""
    normalized_query = query.casefold()

    for item in countries:
        names = item.get("name", {})
        variants = [names.get("common", ""), names.get("official", "")]
        variants.extend(item.get("altSpellings", []))
        if normalized_query in (str(name).casefold() for name in variants):
            return item

    for item in countries:
        common_name = str(item.get("name", {}).get("common", ""))
        if normalized_query in common_name.casefold():
            return item
    return None


def get_country_from_dataset(country: str) -> dict[str, Any] | None:
    """Получить страну из открытого набора v3.1, если старый API отключён."""
    response = requests.get(DATASET_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    countries = response.json()
    if not isinstance(countries, list):
        raise ValueError("сервер вернул данные неожиданного формата")
    return find_country(countries, country)


def get_country(country: str) -> dict[str, Any] | None:
    """Запросить страну и вернуть первую найденную запись."""
    try:
        response = requests.get(
            API_URL.format(country=country),
            params={"fields": "name,capital,region,subregion,languages,currencies,population,area,borders,tld,cca2,timezones,flags"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 404:
            print(Fore.RED + "Страна не найдена. Проверьте название на английском языке.")
            return None

        response.raise_for_status()
        countries = response.json()
        if isinstance(countries, list):
            return countries[0] if countries else None

        # В 2026 году прежний v3.1 endpoint стал возвращать сообщение о
        # деактивации. Открытый JSON того же проекта сохраняет прежнюю схему.
        if isinstance(countries, dict) and countries.get("success") is False:
            result = get_country_from_dataset(country)
            if result is None:
                print(Fore.RED + "Страна не найдена. Проверьте название на английском языке.")
            return result

        raise ValueError("сервер вернул данные неожиданного формата")
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as error:
        print(Fore.RED + f"Не удалось получить данные: {error}")
        return None


def print_country_info(country: dict[str, Any]) -> None:
    """Вывести основные сведения о стране с цветным форматированием."""
    common_name = country.get("name", {}).get("common", "Нет данных")
    official_name = country.get("name", {}).get("official", "Нет данных")
    capital = ", ".join(country.get("capital", [])) or "Нет данных"
    region_parts = [country.get("region"), country.get("subregion")]
    region = ", ".join(part for part in region_parts if part) or "Нет данных"
    languages = format_mapping_values(country.get("languages", {}))
    currencies = format_currencies(country.get("currencies", {}))
    population = f"{country.get('population', 0):,}".replace(",", " ")
    area = f"{country.get('area', 0):,.2f}".replace(",", " ")
    borders = ", ".join(country.get("borders", [])) or "Нет сухопутных границ"
    domains = ", ".join(country.get("tld", [])) or "Нет данных"
    timezones = ", ".join(country.get("timezones", [])) or "Нет данных"
    flags = country.get("flags", {})

    cyan = Fore.CYAN
    white = Fore.WHITE
    yellow = Fore.YELLOW

    print(cyan + "\n" + "=" * 56)
    print(yellow + f"Информация о стране: {common_name}")
    print(cyan + "=" * 56)

    rows = (
        ("Официальное название", official_name),
        ("Столица", capital),
        ("Регион", region),
        ("Языки", languages),
        ("Валюты", currencies),
        ("Население", f"{population} человек"),
        ("Площадь", f"{area} км²"),
        ("Граничит с", borders),
        ("Домены верхнего уровня", domains),
        ("Код страны (ISO)", country.get("cca2", "Нет данных")),
        ("Часовые пояса", timezones),
    )

    for label, value in rows:
        print(cyan + f"{label}: " + white + str(value))

    print(cyan + "\nФлаг: " + white + flags.get("alt", "Описание отсутствует"))
    print(cyan + "Ссылка на изображение флага: " + white + flags.get("png", "Нет данных"))
    print(cyan + "=" * 56 + Style.RESET_ALL)


def main() -> None:
    """Запрашивать страны, пока пользователь не введёт exit."""
    configure_console()
    init(autoreset=True)

    while True:
        prompt = "\nВведите название страны на английском языке (или 'exit' для выхода): "
        country_name = input(Fore.YELLOW + prompt).strip()

        if country_name.lower() == "exit":
            print(Fore.GREEN + "До свидания!")
            break
        if not country_name:
            print(Fore.RED + "Название страны не может быть пустым.")
            continue

        country = get_country(country_name)
        if country:
            print_country_info(country)


if __name__ == "__main__":
    main()
