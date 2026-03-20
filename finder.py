"""
finder.py — Поиск компаний через Google Maps Places API
"""

import os
import time
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
from colorama import Fore, Style

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
SEARCH_CITY = os.getenv("SEARCH_CITY", "Алматы")
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "100"))

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def search_places(query: str, city: str) -> List[Dict]:
    """Ищет места через Google Places Text Search API."""
    results = []
    next_page_token = None
    full_query = f"{query} {city}"

    print(f"{Fore.CYAN}  Поиск: '{full_query}'...{Style.RESET_ALL}")

    while len(results) < MAX_RESULTS:
        params = {
            "query": full_query,
            "key": GOOGLE_MAPS_API_KEY,
            "language": "ru",
        }
        if next_page_token:
            params["pagetoken"] = next_page_token
            time.sleep(2)  # Google требует паузу перед использованием pagetoken

        try:
            resp = requests.get(PLACES_TEXT_SEARCH_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            print(f"{Fore.RED}  Ошибка запроса: {e}{Style.RESET_ALL}")
            break

        status = data.get("status")
        if status == "REQUEST_DENIED":
            print(f"{Fore.RED}  Ошибка API: {data.get('error_message', 'REQUEST_DENIED')}")
            print(f"  Проверьте GOOGLE_MAPS_API_KEY в файле .env{Style.RESET_ALL}")
            break
        if status not in ("OK", "ZERO_RESULTS"):
            print(f"{Fore.YELLOW}  Статус: {status}{Style.RESET_ALL}")
            break

        results.extend(data.get("results", []))
        next_page_token = data.get("next_page_token")

        if not next_page_token or len(results) >= MAX_RESULTS:
            break

    return results[:MAX_RESULTS]


def get_place_details(place_id: str) -> Dict:
    """Получает детали о месте: телефон, сайт, адрес."""
    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,website,formatted_address,rating,user_ratings_total,types",
        "key": GOOGLE_MAPS_API_KEY,
        "language": "ru",
    }
    try:
        resp = requests.get(PLACES_DETAILS_URL, params=params, timeout=10)
        data = resp.json()
        return data.get("result", {})
    except Exception as e:
        print(f"{Fore.RED}  Ошибка получения деталей: {e}{Style.RESET_ALL}")
        return {}


def find_companies(categories: List[str]) -> List[Dict]:
    """
    Основная функция поиска.
    Возвращает список компаний с базовой информацией.
    """
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY == "your_google_maps_api_key_here":
        print(f"{Fore.RED}[!] GOOGLE_MAPS_API_KEY не задан в .env файле{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    Используем демо-данные для тестирования...{Style.RESET_ALL}\n")
        return _get_demo_data()

    all_companies = []
    seen_ids = set()

    for category in categories:
        places = search_places(category, SEARCH_CITY)
        print(f"{Fore.GREEN}  Найдено мест: {len(places)}{Style.RESET_ALL}")

        for place in places:
            place_id = place.get("place_id")
            if place_id in seen_ids:
                continue
            seen_ids.add(place_id)

            details = get_place_details(place_id)
            time.sleep(0.1)  # Чтобы не превысить лимиты API

            company = {
                "name": details.get("name", place.get("name", "")),
                "category": category,
                "address": details.get("formatted_address", place.get("formatted_address", "")),
                "phone": details.get("formatted_phone_number", ""),
                "website": details.get("website", ""),
                "rating": details.get("rating", ""),
                "reviews_count": details.get("user_ratings_total", 0),
                "place_id": place_id,
            }
            all_companies.append(company)

    print(f"\n{Fore.GREEN}Итого уникальных компаний найдено: {len(all_companies)}{Style.RESET_ALL}")
    return all_companies


def _get_demo_data() -> List[Dict]:
    """Демо-данные для тестирования без API ключа."""
    return [
        {
            "name": "Кофейня 'Арома'",
            "category": "кофейня",
            "address": "Алматы, ул. Абая 10",
            "phone": "+7 727 123-45-67",
            "website": "http://aroma-coffee.kz",
            "rating": 4.3,
            "reviews_count": 245,
            "place_id": "demo_1",
        },
        {
            "name": "Салон красоты 'Glamour'",
            "category": "салон красоты",
            "address": "Алматы, пр. Достык 89",
            "phone": "+7 701 987-65-43",
            "website": "",
            "rating": 4.7,
            "reviews_count": 512,
            "place_id": "demo_2",
        },
        {
            "name": "Стоматология 'Дента Плюс'",
            "category": "стоматология",
            "address": "Алматы, ул. Толе би 55",
            "phone": "+7 727 234-56-78",
            "website": "http://denta-plus.kz",
            "rating": 4.8,
            "reviews_count": 891,
            "place_id": "demo_3",
        },
        {
            "name": "Фитнес клуб 'PowerGym'",
            "category": "фитнес клуб",
            "address": "Алматы, ул. Сейфуллина 456",
            "phone": "+7 705 333-22-11",
            "website": "https://powergym.kz",
            "rating": 4.5,
            "reviews_count": 1203,
            "place_id": "demo_4",
        },
        {
            "name": "Ресторан 'Наурыз'",
            "category": "ресторан",
            "address": "Алматы, ул. Панфилова 112",
            "phone": "+7 727 555-44-33",
            "website": "https://nauryz-restaurant.kz",
            "rating": 4.6,
            "reviews_count": 678,
            "place_id": "demo_5",
        },
        {
            "name": "Автосервис 'АвтоМастер'",
            "category": "автосервис",
            "address": "Алматы, ул. Рыскулова 200",
            "phone": "+7 701 444-33-22",
            "website": "",
            "rating": 4.2,
            "reviews_count": 189,
            "place_id": "demo_6",
        },
        {
            "name": "Отель 'Comfort Inn'",
            "category": "отель",
            "address": "Алматы, ул. Гоголя 73",
            "phone": "+7 727 666-77-88",
            "website": "http://comfort-inn.kz",
            "rating": 4.0,
            "reviews_count": 324,
            "place_id": "demo_7",
        },
        {
            "name": "Аптека 'Здоровье'",
            "category": "аптека",
            "address": "Алматы, пр. Аль-Фараби 17",
            "phone": "+7 727 888-99-00",
            "website": "",
            "rating": 4.4,
            "reviews_count": 156,
            "place_id": "demo_8",
        },
    ]
