"""
main.py — Точка входа. Запускает полный pipeline поиска лидов.

Использование:
    python main.py
    python main.py --city "Астана" --categories "ресторан,кафе,отель"
    python main.py --demo                  # Запустить с демо-данными (без API ключа)
    python main.py --send-emails           # Найти + отправить письма
    python main.py --send-emails --dry-run # Проверить без реальной отправки
"""

import os
import sys
import time
import argparse
from dotenv import load_dotenv
from colorama import init, Fore, Style
from tqdm import tqdm

from finder import find_companies
from analyzer import analyze_website
from app_checker import check_mobile_apps
from reporter import generate_report
from emailer import run_email_campaign

init(autoreset=True)
load_dotenv()

# Настраиваем вывод UTF-8 для Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BANNER = f"""
{Fore.CYAN}+------------------------------------------------------+
|       WorkWork Studio -- Lead Finder v1.0            |
|    Поиск компаний для outbound-продаж                |
+------------------------------------------------------+{Style.RESET_ALL}
"""


def parse_args():
    parser = argparse.ArgumentParser(description="WorkWork Studio Lead Finder")
    parser.add_argument("--city", default=None, help="Город поиска (например: Алматы)")
    parser.add_argument("--categories", default=None, help="Категории через запятую")
    parser.add_argument("--demo", action="store_true", help="Запустить с демо-данными")
    parser.add_argument("--no-app-check", action="store_true", help="Пропустить проверку приложений")
    parser.add_argument("--send-emails", action="store_true", help="Отправить письма найденным компаниям")
    parser.add_argument("--dry-run", action="store_true", help="Тест рассылки без реальной отправки")
    return parser.parse_args()


def main():
    print(BANNER)
    args = parse_args()

    # Переопределяем .env если переданы аргументы
    if args.city:
        os.environ["SEARCH_CITY"] = args.city
    if args.demo:
        os.environ["GOOGLE_MAPS_API_KEY"] = ""

    city = os.getenv("SEARCH_CITY", "Алматы")
    raw_categories = os.getenv(
        "SEARCH_CATEGORIES",
        "ресторан,салон красоты,стоматология,фитнес клуб,автосервис"
    )

    if args.categories:
        raw_categories = args.categories

    categories = [c.strip() for c in raw_categories.split(",") if c.strip()]

    print(f"{Fore.WHITE}Город:      {Fore.YELLOW}{city}")
    print(f"{Fore.WHITE}Категории:  {Fore.YELLOW}{', '.join(categories)}")
    print(f"{Fore.WHITE}Режим:      {Fore.YELLOW}{'ДЕМО (без API)' if not os.getenv('GOOGLE_MAPS_API_KEY') else 'Google Maps API'}")
    print()

    # ─── Шаг 1: Поиск компаний ───────────────────────────────────────────────
    print(f"{Fore.CYAN}{'─'*54}")
    print(f"{Fore.CYAN}[1/3] Поиск компаний через Google Maps...{Style.RESET_ALL}")
    companies = find_companies(categories)

    if not companies:
        print(f"{Fore.RED}Компании не найдены. Проверьте настройки.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.GREEN}✓ Найдено: {len(companies)} компаний{Style.RESET_ALL}\n")

    # ─── Шаг 2: Анализ сайтов ────────────────────────────────────────────────
    print(f"{Fore.CYAN}{'─'*54}")
    print(f"{Fore.CYAN}[2/3] Анализ сайтов...{Style.RESET_ALL}")

    with_website = [c for c in companies if c.get("website")]
    without_website = [c for c in companies if not c.get("website")]

    print(f"  Есть сайт: {len(with_website)}, нет сайта: {len(without_website)}\n")

    for company in tqdm(companies, desc="  Анализ", unit="сайт", ncols=60):
        if company.get("website"):
            company["site_analysis"] = analyze_website(company["website"])
            time.sleep(0.2)
        else:
            company["site_analysis"] = analyze_website("")

    print(f"{Fore.GREEN}✓ Анализ сайтов завершён{Style.RESET_ALL}\n")

    # ─── Шаг 3: Проверка мобильных приложений ────────────────────────────────
    print(f"{Fore.CYAN}{'─'*54}")
    print(f"{Fore.CYAN}[3/3] Проверка мобильных приложений...{Style.RESET_ALL}")

    if args.no_app_check:
        print(f"  {Fore.YELLOW}Пропущено (флаг --no-app-check){Style.RESET_ALL}")
        for company in companies:
            company["app_check"] = {
                "has_mobile_app": False,
                "app_status": "Не проверялось",
                "ios_app": False, "android_app": False,
                "ios_link": "", "android_link": ""
            }
    else:
        for company in tqdm(companies, desc="  Проверка", unit="компания", ncols=60):
            company["app_check"] = check_mobile_apps(company["name"])
            time.sleep(0.2)

    print(f"{Fore.GREEN}✓ Проверка приложений завершена{Style.RESET_ALL}\n")

    # ─── Шаг 4: Генерация отчёта ─────────────────────────────────────────────
    print(f"{Fore.CYAN}{'─'*54}")
    print(f"{Fore.CYAN}Генерация Excel-отчёта...{Style.RESET_ALL}")

    report_path = generate_report(companies)

    # ─── Итоги ───────────────────────────────────────────────────────────────
    hot_leads = [c for c in companies if _is_hot(c)]
    no_site = [c for c in companies if not c.get("website")]
    no_app = [c for c in companies if not c.get("app_check", {}).get("has_mobile_app")]
    outdated = [
        c for c in companies
        if c.get("site_analysis", {}).get("score", 100) < 45 and c.get("website")
    ]

    # ─── Шаг 5: Рассылка ─────────────────────────────────────────────────────
    if args.send_emails:
        hot_leads = [c for c in companies if _is_hot(c)]
        run_email_campaign(hot_leads, dry_run=args.dry_run)

    print(f"""
{Fore.GREEN}{'═'*54}
✅ ГОТОВО!
{'═'*54}{Style.RESET_ALL}

{Fore.WHITE}📊 Результаты анализа:{Style.RESET_ALL}
   Всего компаний:          {Fore.YELLOW}{len(companies)}{Style.RESET_ALL}
   Нет сайта:               {Fore.RED}{len(no_site)}{Style.RESET_ALL}
   Устаревший сайт:         {Fore.RED}{len(outdated)}{Style.RESET_ALL}
   Нет мобильного приложения: {Fore.RED}{len(no_app)}{Style.RESET_ALL}
   🔥 Горячих лидов:        {Fore.GREEN}{len(hot_leads)}{Style.RESET_ALL}

{Fore.WHITE}📁 Отчёт сохранён:{Style.RESET_ALL}
   {Fore.CYAN}{report_path}{Style.RESET_ALL}

{Fore.WHITE}Следующий шаг:{Style.RESET_ALL}
   Откройте файл → лист "🔥 Горячие лиды" →
   используйте готовые шаблоны писем из листа "📧 Шаблоны писем"
""")


def _is_hot(company: dict) -> bool:
    site_score = company.get("site_analysis", {}).get("score", 50)
    has_app = company.get("app_check", {}).get("has_mobile_app", True)
    has_website = bool(company.get("website"))
    return (not has_website or site_score < 45) and not has_app


if __name__ == "__main__":
    main()
