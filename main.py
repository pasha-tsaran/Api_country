"""Интерактивный модуль для ручного тестирования HTTP-запросов."""

from __future__ import annotations

import json
import sys
from typing import Any

import requests
from colorama import init


REQUEST_TIMEOUT = 15


def configure_console() -> None:
    """Включить UTF-8 для корректного вывода JSON в Windows-консоли."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def print_response(response: requests.Response) -> None:
    """Вывести код ответа и его тело в удобном виде."""
    print(f"\nСтатус ответа: {response.status_code}")

    try:
        body = response.json()
    except requests.exceptions.JSONDecodeError:
        print(response.text or "<пустое тело ответа>")
    else:
        print(json.dumps(body, ensure_ascii=False, indent=2))


def make_get_request(url: str) -> requests.Response | None:
    """Выполнить GET-запрос по произвольному URL."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        print_response(response)
        return response
    except requests.exceptions.RequestException as error:
        print(f"Ошибка GET-запроса: {error}")
        return None


def make_post_request(url: str, data: dict[str, Any] | None = None) -> None:
    """Выполнить POST-запрос, отправив словарь как JSON."""
    try:
        response = requests.post(url, json=data, timeout=REQUEST_TIMEOUT)
        print_response(response)
    except requests.exceptions.RequestException as error:
        print(f"Ошибка POST-запроса: {error}")


def make_get_country_request(country: str) -> None:
    """Получить страну и вывести только полезные сведения, без полного JSON."""
    from country_info import get_country, print_country_info

    country_data = get_country(country)
    if country_data:
        print_country_info(country_data)


def read_json_body() -> dict[str, Any] | None:
    """Прочитать необязательное JSON-тело POST-запроса из консоли."""
    raw_data = input("Введите JSON-тело (или нажмите Enter без тела): ").strip()
    if not raw_data:
        return None

    try:
        parsed_data = json.loads(raw_data)
    except json.JSONDecodeError as error:
        print(f"Некорректный JSON: {error}")
        return None

    if not isinstance(parsed_data, dict):
        print("JSON-тело должно быть объектом, например: {\"name\": \"Alex\"}")
        return None
    return parsed_data


def main() -> None:
    """Показать меню и запустить выбранный тип запроса."""
    configure_console()
    init(autoreset=True)

    while True:
        print("\nВыберите действие:")
        print("1. Выполнить GET-запрос")
        print("2. Выполнить POST-запрос")
        print("3. Получить информацию о стране")
        print("4. Выйти")

        choice = input("Ваш выбор: ").strip()

        if choice == "1":
            url = input("Введите URL: ").strip()
            make_get_request(url)
        elif choice == "2":
            url = input("Введите URL: ").strip()
            make_post_request(url, read_json_body())
        elif choice == "3":
            country = input("Введите название страны на английском языке: ").strip()
            make_get_country_request(country)
        elif choice == "4":
            print("До свидания!")
            break
        else:
            print("Введите номер от 1 до 4.")


if __name__ == "__main__":
    main()
