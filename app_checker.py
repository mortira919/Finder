"""
app_checker.py — Проверяет наличие мобильного приложения в App Store и Google Play
"""

import re
import time
import requests
from typing import Dict, Tuple
from urllib.parse import quote

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
GPLAY_SEARCH_URL = "https://play.google.com/store/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def check_app_store(company_name: str) -> Tuple[bool, str]:
    """
    Ищет приложение в App Store через iTunes Search API.
    Возвращает (найдено, ссылка_или_пусто).
    """
    params = {
        "term": company_name,
        "country": "kz",
        "media": "software",
        "limit": 5,
    }
    try:
        resp = requests.get(ITUNES_SEARCH_URL, params=params, timeout=8)
        data = resp.json()
        results = data.get("results", [])

        for app in results:
            app_name = app.get("trackName", "").lower()
            search_name = company_name.lower()
            # Проверяем схожесть названий
            if _names_match(search_name, app_name):
                return True, app.get("trackViewUrl", "")

        return False, ""
    except Exception:
        return False, ""


def check_google_play(company_name: str) -> Tuple[bool, str]:
    """
    Ищет приложение в Google Play через скрапинг страницы поиска.
    Возвращает (найдено, ссылка_или_пусто).
    """
    search_url = f"{GPLAY_SEARCH_URL}?q={quote(company_name)}&c=apps&hl=ru"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        content = resp.text

        # Ищем ссылки на приложения в HTML
        pattern = r'/store/apps/details\?id=([\w.]+)'
        app_ids = re.findall(pattern, content)

        if app_ids:
            # Берём первый результат и проверяем схожесть
            first_app_id = app_ids[0]
            # Пытаемся найти название приложения рядом с ID
            app_link = f"https://play.google.com/store/apps/details?id={first_app_id}"

            # Грубая проверка — ищем название компании на странице результатов
            company_words = company_name.lower().split()
            content_lower = content.lower()
            matches = sum(1 for word in company_words if len(word) > 3 and word in content_lower)

            if matches >= 1 or len(company_words) == 1:
                return True, app_link

        return False, ""
    except Exception:
        return False, ""


def check_mobile_apps(company_name: str) -> Dict:
    """
    Полная проверка наличия мобильных приложений.
    Возвращает словарь с результатами.
    """
    ios_found, ios_link = check_app_store(company_name)
    time.sleep(0.3)
    android_found, android_link = check_google_play(company_name)

    has_app = ios_found or android_found

    return {
        "has_mobile_app": has_app,
        "ios_app": ios_found,
        "ios_link": ios_link,
        "android_app": android_found,
        "android_link": android_link,
        "app_status": _get_app_status(ios_found, android_found),
    }


def _get_app_status(ios: bool, android: bool) -> str:
    if ios and android:
        return "Есть iOS + Android"
    elif ios:
        return "Только iOS"
    elif android:
        return "Только Android"
    else:
        return "Нет приложения"


def _names_match(search: str, found: str) -> bool:
    """Простая проверка совпадения названий."""
    search_words = [w for w in search.split() if len(w) > 2]
    if not search_words:
        return False
    matches = sum(1 for w in search_words if w in found)
    return matches / len(search_words) >= 0.5
