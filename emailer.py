"""
emailer.py — Авторассылка холодных писем найденным компаниям
"""

import os
import time
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Tuple
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
EMAIL_DELAY = int(os.getenv("EMAIL_DELAY", "5"))


def extract_emails_from_website(url: str) -> List[str]:
    """Пытается найти email на сайте компании."""
    if not url:
        return []
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=8)
        emails = re.findall(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
            resp.text
        )
        # Фильтруем мусор (иконки, CSS и т.д.)
        real_emails = [
            e for e in set(emails)
            if not any(x in e.lower() for x in [
                '.png', '.jpg', '.svg', '.css', '.js',
                'example', 'test', 'noreply', 'no-reply'
            ])
        ]
        return real_emails[:3]  # Максимум 3 адреса с сайта
    except Exception:
        return []


def send_email(to_email: str, subject: str, body: str) -> Tuple[bool, str]:
    """
    Отправляет одно письмо через Gmail SMTP.
    Возвращает (успех, сообщение).
    """
    if not SENDER_EMAIL or SENDER_EMAIL == "your_email@gmail.com":
        return False, "SENDER_EMAIL не настроен в .env"
    if not SENDER_PASSWORD or SENDER_PASSWORD == "xxxx xxxx xxxx xxxx":
        return False, "SENDER_PASSWORD не настроен в .env"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"WorkWork Studio <{SENDER_EMAIL}>"
        msg["To"] = to_email

        # Текстовая версия
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # HTML версия
        html_body = _to_html(body)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

        return True, "Отправлено"

    except smtplib.SMTPAuthenticationError:
        return False, "Ошибка авторизации — проверьте App Password в .env"
    except smtplib.SMTPRecipientsRefused:
        return False, "Адрес отклонён сервером"
    except Exception as e:
        return False, str(e)[:80]


def run_email_campaign(companies: List[Dict], dry_run: bool = False) -> Dict:
    """
    Основная функция рассылки.
    dry_run=True — только показывает что будет отправлено, не отправляет.
    """
    from reporter import _generate_email_body, _get_email_subject

    print(f"\n{Fore.CYAN}{'─'*54}")
    print(f"{Fore.CYAN}📧 Авторассылка{' (DRY RUN — письма не отправляются)' if dry_run else ''}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─'*54}{Style.RESET_ALL}\n")

    if not dry_run and (
        not SENDER_EMAIL or SENDER_EMAIL == "your_email@gmail.com"
    ):
        print(f"{Fore.RED}[!] Настройте SENDER_EMAIL и SENDER_PASSWORD в .env{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}    Инструкция: google.com → Аккаунт → Безопасность → Двухэтапная → App Passwords{Style.RESET_ALL}")
        return {"sent": 0, "failed": 0, "no_email": 0}

    stats = {"sent": 0, "failed": 0, "no_email": 0, "results": []}

    for i, company in enumerate(companies, 1):
        name = company.get("name", "")
        website = company.get("website", "")

        print(f"[{i}/{len(companies)}] {name}")

        # Ищем email на сайте
        emails = extract_emails_from_website(website) if website else []

        if not emails:
            print(f"  {Fore.YELLOW}Email не найден{Style.RESET_ALL}")
            stats["no_email"] += 1
            stats["results"].append({
                "company": name, "status": "Нет email", "email": ""
            })
            continue

        target_email = emails[0]
        subject = _get_email_subject(company)
        body = _generate_email_body(company)

        print(f"  Email: {target_email}")
        print(f"  Тема:  {subject}")

        if dry_run:
            print(f"  {Fore.YELLOW}[DRY RUN] Письмо не отправлено{Style.RESET_ALL}")
            stats["sent"] += 1
            stats["results"].append({
                "company": name, "status": "DRY RUN", "email": target_email
            })
        else:
            success, message = send_email(target_email, subject, body)
            if success:
                print(f"  {Fore.GREEN}✓ Отправлено{Style.RESET_ALL}")
                stats["sent"] += 1
                stats["results"].append({
                    "company": name, "status": "Отправлено", "email": target_email
                })
            else:
                print(f"  {Fore.RED}✗ Ошибка: {message}{Style.RESET_ALL}")
                stats["failed"] += 1
                stats["results"].append({
                    "company": name, "status": f"Ошибка: {message}", "email": target_email
                })

            time.sleep(EMAIL_DELAY)  # Пауза между письмами

        print()

    # Итоги
    print(f"{Fore.GREEN}{'─'*54}")
    print(f"Итог рассылки:")
    print(f"  Отправлено:   {stats['sent']}")
    print(f"  Ошибок:       {stats['failed']}")
    print(f"  Нет email:    {stats['no_email']}{Style.RESET_ALL}")

    return stats


def _to_html(text: str) -> str:
    """Конвертирует plain text в простой HTML."""
    lines = text.split("\n")
    html_lines = []
    for line in lines:
        if line.startswith("•"):
            html_lines.append(f"<li>{line[1:].strip()}</li>")
        elif line == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p style='margin:4px 0'>{line}</p>")

    return f"""
    <html><body style="font-family: Arial, sans-serif; font-size: 14px; color: #222; max-width: 600px;">
    {''.join(html_lines)}
    <br><hr style="border:none;border-top:1px solid #eee">
    <p style="color:#888;font-size:12px">
        WorkWork Studio — разработка мобильных приложений и веб-сервисов<br>
        <a href="https://workworkstudio.pro">workworkstudio.pro</a>
    </p>
    </body></html>
    """
