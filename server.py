"""
server.py — FastAPI веб-сервер для WorkWork Studio Lead Finder
"""

import os
import uuid
import json
import asyncio
import threading
import time
from typing import Dict, Optional
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WorkWork Lead Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище активных задач
jobs: Dict[str, dict] = {}


def run_search(job_id: str, city: str, country: str, categories: list, api_key: str):
    """Запускает поиск в отдельном потоке."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    os.environ["GOOGLE_MAPS_API_KEY"] = api_key
    os.environ["SEARCH_CITY"] = city
    os.environ["COUNTRY"] = country
    os.environ["SEARCH_CATEGORIES"] = ",".join(categories)
    os.environ["MAX_RESULTS"] = "20"

    job = jobs[job_id]

    try:
        from finder import find_companies
        from analyzer import analyze_website
        from reporter import generate_report

        # Шаг 1
        job["status"] = "searching"
        job["message"] = f"Ищем компании в {city}..."
        job["progress"] = 5

        companies = find_companies(categories)
        job["total"] = len(companies)
        job["message"] = f"Найдено {len(companies)} компаний. Анализируем сайты..."
        job["progress"] = 20

        # Шаг 2
        job["status"] = "analyzing"
        for i, company in enumerate(companies):
            if company.get("website"):
                company["site_analysis"] = analyze_website(company["website"])
                time.sleep(0.1)
            else:
                company["site_analysis"] = analyze_website("")

            company["app_check"] = {
                "has_mobile_app": False,
                "app_status": "Не проверялось",
                "ios_app": False, "android_app": False,
                "ios_link": "", "android_link": ""
            }

            progress = 20 + int((i + 1) / len(companies) * 70)
            job["progress"] = progress
            job["message"] = f"Анализируем сайты... {i+1}/{len(companies)}"

        # Шаг 3
        job["status"] = "generating"
        job["message"] = "Генерируем отчёт..."
        job["progress"] = 95

        from reporter import _is_hot_lead
        hot = [c for c in companies if _is_hot_lead(c)]

        filepath = generate_report(companies, country=country)
        job["status"] = "done"
        job["progress"] = 100
        job["file"] = filepath
        job["hot_count"] = len(hot)
        job["total_count"] = len(companies)
        job["no_site_count"] = sum(1 for c in companies if not c.get("website"))
        job["message"] = f"Готово! Найдено {len(hot)} горячих лидов."

    except Exception as e:
        job["status"] = "error"
        job["message"] = f"Ошибка: {str(e)}"
        job["progress"] = 0


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/search")
async def start_search(request: Request):
    data = await request.json()
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "message": "Запуск...",
        "file": None,
        "hot_count": 0,
        "total_count": 0,
        "no_site_count": 0,
    }

    thread = threading.Thread(
        target=run_search,
        args=(
            job_id,
            data.get("city", "Алматы"),
            data.get("country", "KZ"),
            data.get("categories", ["ресторан", "салон красоты", "стоматология",
                                    "фитнес клуб", "автосервис", "отель", "аптека"]),
            data.get("api_key", os.getenv("GOOGLE_MAPS_API_KEY", "")),
        ),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


@app.get("/api/download/{job_id}")
async def download(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("file"):
        return {"error": "File not found"}
    filepath = job["file"]
    filename = os.path.basename(filepath)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
