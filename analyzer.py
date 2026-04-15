"""
analyzer.py — Анализирует сайт компании на устаревшесть и качество
"""

import re
import time
import requests
from typing import Dict, Optional
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Устаревшие технологии — явный сигнал для нас
OUTDATED_TECH_PATTERNS = {
    "jQuery 1.x / 2.x": [r"jquery[.-]1\.\d", r"jquery[.-]2\.\d"],
    "Flash": [r"\.swf", r"application/x-shockwave-flash"],
    "Bootstrap 2.x / 3.x": [r"bootstrap[.-]2\.\d", r"bootstrap[.-]3\.\d"],
    "PHP 5.x признаки": [r"powered by php/5", r"x-powered-by: php/5"],
    "WordPress старый": [r"wp-content.*ver=\d\.\d", r"wordpress \d\.\d"],
    "Table-based layout": [r"<table.*?layout", r'<td.*?width="\d+%"'],
    "Internet Explorer": [r"<!--\[if IE\]>", r"<!--\[if lt IE"],
    "Устаревший meta": [r'<meta\s+http-equiv="refresh"'],
}

# Современные признаки хорошего сайта
MODERN_TECH_PATTERNS = {
    "React": [r"react\.min\.js", r"react-dom", r'data-reactroot', r"__NEXT_DATA__"],
    "Vue.js": [r"vue\.min\.js", r"vue@\d", r"__vue__"],
    "Next.js": [r"__NEXT_DATA__", r"_next/static"],
    "Flutter Web": [r"flutter\.js", r"flutter_service_worker"],
    "PWA": [r'rel="manifest"', r"service.?worker"],
    "HTTPS": [],  # Проверяется отдельно
    "Адаптивный": [],  # Проверяется отдельно
}


def analyze_website(url: str) -> Dict:
    """
    Анализирует сайт и возвращает оценку устаревшести.
    """
    if not url:
        return _no_website_result()

    # Нормализуем URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    result = {
        "url": url,
        "reachable": False,
        "has_ssl": url.startswith("https://"),
        "is_mobile_friendly": False,
        "has_viewport": False,
        "load_time_ms": 0,
        "outdated_signals": [],
        "modern_signals": [],
        "copyright_year": None,
        "score": 0,           # 0-100, чем ниже — тем лучше для нас (старее сайт)
        "verdict": "",
        "opportunity": "",
    }

    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        result["load_time_ms"] = int((time.time() - start) * 1000)
        result["reachable"] = True
        result["has_ssl"] = resp.url.startswith("https://")

        # Если редирект на https — обновляем
        if resp.url != url:
            result["url"] = resp.url

        html = resp.text.lower()
        soup = BeautifulSoup(resp.text, "lxml")

        # --- Проверка адаптивности ---
        viewport = soup.find("meta", attrs={"name": "viewport"})
        result["has_viewport"] = viewport is not None
        result["is_mobile_friendly"] = (
            viewport is not None and
            "width=device-width" in (viewport.get("content", "").lower())
        )

        # --- Устаревшие технологии ---
        for tech_name, patterns in OUTDATED_TECH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    result["outdated_signals"].append(tech_name)
                    break

        # --- Современные технологии ---
        for tech_name, patterns in MODERN_TECH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    result["modern_signals"].append(tech_name)
                    break

        # --- Год в копирайте ---
        copyright_match = re.search(
            r'(?:©|copyright|&copy;)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})',
            html, re.IGNORECASE
        )
        if copyright_match:
            result["copyright_year"] = int(copyright_match.group(1))

        # --- Соцсети ---
        result["socials"] = _extract_socials(soup, resp.text)

        # --- Подсчёт итогового скора ---
        result["score"] = _calculate_score(result)
        result["verdict"] = _get_verdict(result)
        result["opportunity"] = _get_opportunity(result)

        if "socials" not in result:
            result["socials"] = {}

    except requests.exceptions.SSLError:
        result["reachable"] = True
        result["has_ssl"] = False
        result["score"] = 20
        result["verdict"] = "Проблемы с SSL сертификатом"
        result["opportunity"] = "Требуется обновление"
    except requests.exceptions.ConnectionError:
        result["verdict"] = "Сайт недоступен"
        result["opportunity"] = "Сайт не работает — отличный повод предложить новый"
    except Exception as e:
        result["verdict"] = f"Ошибка анализа: {str(e)[:50]}"

    return result


def _calculate_score(r: Dict) -> int:
    """
    Считает оценку современности сайта (0-100).
    0 = очень старый/плохой, 100 = отличный современный сайт.
    Нам нужны компании с низким скором!
    """
    score = 50  # Базовый

    # Плюсы (современные признаки)
    if r["has_ssl"]:
        score += 15
    if r["is_mobile_friendly"]:
        score += 20
    score += len(r["modern_signals"]) * 8

    # Минусы (устаревшие признаки)
    score -= len(r["outdated_signals"]) * 12

    # Год копирайта
    current_year = datetime.now().year
    if r.get("copyright_year"):
        age = current_year - r["copyright_year"]
        if age >= 5:
            score -= 20
        elif age >= 3:
            score -= 10

    # Медленная загрузка
    if r["load_time_ms"] > 5000:
        score -= 10
    elif r["load_time_ms"] > 3000:
        score -= 5

    return max(0, min(100, score))


def _get_verdict(r: Dict) -> str:
    score = r.get("score", 50)
    if score <= 25:
        return "Очень устаревший сайт"
    elif score <= 45:
        return "Устаревший сайт"
    elif score <= 65:
        return "Средний уровень"
    elif score <= 80:
        return "Хороший сайт"
    else:
        return "Современный сайт"


def _get_opportunity(r: Dict) -> str:
    """Формирует конкретную боль / возможность для продажи."""
    issues = []

    if not r["reachable"]:
        return "Сайт не работает — нужна полная переработка"
    if not r["has_ssl"]:
        issues.append("нет HTTPS")
    if not r["is_mobile_friendly"]:
        issues.append("не адаптирован под мобильные")
    if r.get("outdated_signals"):
        issues.append(f"устаревшие технологии ({', '.join(r['outdated_signals'][:2])})")

    year = r.get("copyright_year")
    if year and (datetime.now().year - year) >= 4:
        issues.append(f"сайт не обновлялся с {year} года")

    if issues:
        return "Проблемы: " + "; ".join(issues)
    elif r.get("score", 50) < 60:
        return "Есть потенциал для улучшения"
    else:
        return "Сайт в порядке"


def _extract_socials(soup, raw_html: str) -> Dict:
    """Ищет ссылки на соцсети на странице компании."""
    socials = {}
    raw_lower = raw_html.lower()

    patterns = {
        "instagram": r'instagram\.com/([A-Za-z0-9_.]{2,30})/?(?:["\'\s]|$)',
        "vk":        r'vk\.com/([A-Za-z0-9_.]{2,50})/?(?:["\'\s]|$)',
        "telegram":  r't\.me/([A-Za-z0-9_]{3,32})/?(?:["\'\s]|$)',
        "youtube":   r'youtube\.com/(?:channel/|@)([A-Za-z0-9_\-]{2,50})',
        "whatsapp":  r'wa\.me/(\d{10,15})',
    }

    for platform, pattern in patterns.items():
        match = re.search(pattern, raw_html, re.IGNORECASE)
        if match:
            username = match.group(1)
            # Фильтруем мусор (общие слова, трекеры)
            skip = {"share", "sharer", "intent", "p", "feed", "stories",
                    "explore", "reel", "reels", "accounts", "privacy"}
            if username.lower() not in skip and len(username) > 2:
                if platform == "instagram":
                    socials["instagram"] = f"instagram.com/{username}"
                elif platform == "vk":
                    socials["vk"] = f"vk.com/{username}"
                elif platform == "telegram":
                    socials["telegram"] = f"t.me/{username}"
                elif platform == "youtube":
                    socials["youtube"] = f"youtube.com/@{username}"
                elif platform == "whatsapp":
                    socials["whatsapp"] = f"wa.me/{username}"

    return socials


def _no_website_result() -> Dict:
    return {
        "url": "",
        "reachable": False,
        "has_ssl": False,
        "is_mobile_friendly": False,
        "has_viewport": False,
        "load_time_ms": 0,
        "outdated_signals": [],
        "modern_signals": [],
        "copyright_year": None,
        "score": 0,
        "verdict": "Нет сайта",
        "opportunity": "Нет сайта — предложить разработку с нуля",
    }
