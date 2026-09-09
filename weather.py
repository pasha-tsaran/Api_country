import os

import requests
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("API_KEY")

GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
REQUEST_TIMEOUT = 10


class WeatherAppError(Exception):
    """Ожидаемая ошибка приложения, которую можно показать пользователю."""


def _check_api_key() -> None:
    if not API_KEY:
        raise WeatherAppError(
            "API-ключ не найден. Добавьте строку API_KEY=ваш_ключ в файл .env."
        )


def _check_response(response: requests.Response) -> None:
    if response.status_code == 401:
        raise WeatherAppError(
            "API-ключ недействителен или ещё не активирован. Проверьте API_KEY в .env."
        )
    if response.status_code != 200:
        raise WeatherAppError(
            f"Сервис OpenWeather вернул ошибку (статус {response.status_code})."
        )


def get_coordinates(city: str) -> tuple[float, float]:
    """Возвращает широту и долготу первого найденного города."""
    _check_api_key()

    try:
        response = requests.get(
            GEOCODING_URL,
            params={"q": city, "limit": 1, "lang": "ru", "appid": API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise WeatherAppError(
            "Не удалось подключиться к OpenWeather. Проверьте интернет-соединение."
        ) from error

    _check_response(response)

    try:
        locations = response.json()
    except requests.JSONDecodeError as error:
        raise WeatherAppError("OpenWeather вернул некорректный ответ.") from error

    if not locations:
        raise WeatherAppError(f"Город «{city}» не найден.")

    try:
        return float(locations[0]["lat"]), float(locations[0]["lon"])
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise WeatherAppError("В ответе OpenWeather нет координат города.") from error


def get_weather_by_coordinates(lat: float, lon: float) -> dict:
    """Возвращает текущую погоду для переданных координат."""
    _check_api_key()

    try:
        response = requests.get(
            CURRENT_WEATHER_URL,
            params={
                "lat": lat,
                "lon": lon,
                "appid": API_KEY,
                "units": "metric",
                "lang": "ru",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise WeatherAppError(
            "Не удалось подключиться к OpenWeather. Проверьте интернет-соединение."
        ) from error

    _check_response(response)

    try:
        return response.json()
    except requests.JSONDecodeError as error:
        raise WeatherAppError("OpenWeather вернул некорректный ответ.") from error


def main() -> None:
    city = input("Введите город: ").strip()
    if not city:
        print("Ошибка: название города не может быть пустым.")
        return

    try:
        lat, lon = get_coordinates(city)
        weather = get_weather_by_coordinates(lat, lon)
        temperature = weather["main"]["temp"]
        description = weather["weather"][0]["description"]
    except WeatherAppError as error:
        print(f"Ошибка: {error}")
        return
    except (KeyError, TypeError, IndexError):
        print("Ошибка: в ответе OpenWeather отсутствуют данные о погоде.")
        return

    print(f"Погода в {city}: {temperature}°C, {description}")


if __name__ == "__main__":
    main()
