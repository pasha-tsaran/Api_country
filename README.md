## Курсы валют (`currency.py`)

Установите зависимости и запустите модуль:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirement.txt
python currency.py
```

После запуска появится меню конвертера. В нём можно конвертировать любую сумму,
посмотреть все доступные коды, получить информацию о конкретной валюте или
принудительно обновить курсы. Ответ API сохраняется в `currency_rate.json` и
повторно используется в течение 24 часов.

Пять ключевых полей ответа `latest`: `base_code`, `time_last_update_utc`,
`time_next_update_utc`, `rates.RUB` и `rates.USD`. У открытого endpoint таблица
называется `rates` (поле `conversion_rates` используется в API с ключом).
Документация и источник курсов: [ExchangeRate-API](https://www.exchangerate-api.com/docs/free).

## Запуск

```
.\venv\Scripts\Activate.ps1
pip install -r requirement.txt
```

Универсальный тестовый модуль с GET, POST и запросом страны:

```
python api_tester.py
```

Отдельный цветной справочник стран:

```
python country_info.py
```

Для завершения справочника введите
`exit`.
