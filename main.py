import os
import json
import base64
from typing import List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("GEMINI_API_KEY topilmadi!")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"

app = FastAPI(title="Gemini Navigation API — Address + PDF optional")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def build_google_maps_link(origin: str, destination: str) -> str:
    params = {"api": "1", "origin": origin, "destination": destination}
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


async def extract_address_from_pdf(pdf: UploadFile) -> Optional[str]:
    """ PDF -> manzil parsing (Gemini orqali) """

    content = await pdf.read()
    if not content:
        return None

    inline_pdf = {
        "inlineData": {
            "data": pdf_to_base64(content),
            "mimeType": "application/pdf",
        }
    }

    prompt = """
Read the permit PDF. Extract ONLY the main pickup or delivery CITY + STATE or full address.
Return only plain text like: "Rhome, TX" or "Boone, CO".
If highway descriptions exist, convert to nearest city name.
No JSON. No extra text.
"""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                inline_pdf
            ]
        }]
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        raise HTTPException(500, f"Gemini error: {r.text}")

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except:
        return None


@app.post("/api/generate-navigation-link")
async def generate(
    # TEXT address (optional)
    start_address: str = Form(""),
    end_address: str = Form(""),

    # PDF address (optional)
    start_file: Optional[UploadFile] = File(None),
    end_file: Optional[UploadFile] = File(None),
):
    # --- START ADDRESS ---
    if start_file:
        start_address = await extract_address_from_pdf(start_file)

    if not start_address:
        raise HTTPException(400, "Starting address topilmadi (PDF yoki text).")

    # --- END ADDRESS ---
    if end_file:
        end_address = await extract_address_from_pdf(end_file)

    if not end_address:
        raise HTTPException(400, "Destination address topilmadi (PDF yoki text).")

    link = build_google_maps_link(start_address, end_address)

    return {
        "success": True,
        "origin": start_address,
        "destination": end_address,
        "notes": "Addresses extracted from text/PDF successfully.",
        "google_maps_link": link,
    }
