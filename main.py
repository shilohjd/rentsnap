"""
main.py
-------
FastAPI app for RentSnap.

Routes
------
GET  /           Homepage — shows form + report counter
POST /generate   Accepts form data, runs agent, returns results page
GET  /health     Railway health check (required for deployment)
"""

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from typing import List, Optional

from database import init_db, increment_and_get, get_count
from agent_wrapper import generate_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request":      request,
            "count":        get_count(),
            "show_results": False,
        }
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request:       Request,
    address:       str            = Form(...),
    beds:          int            = Form(...),
    baths:         float          = Form(...),
    property_type: str            = Form(default="House"),
    current_rent:  Optional[str]  = Form(default=None),
    amenities:     List[str]      = Form(default=[]),
):
    report_html = generate_report(
        address=address,
        beds=beds,
        baths=baths,
        property_type=property_type,
        current_rent=current_rent,
        amenities=amenities,
    )

    new_count = increment_and_get()

    return templates.TemplateResponse(
        "index.html",
        {
            "request":       request,
            "count":         new_count,
            "show_results":  True,
            "report_html":   report_html,
            "address":       address,
            "beds":          beds,
            "baths":         baths,
            "property_type": property_type,
            "current_rent":  current_rent,
            "amenities":     amenities,
        }
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
