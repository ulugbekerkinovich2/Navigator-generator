import os
import json
import base64
from typing import List
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# .env ichida:
# GEMINI_API_KEY=.....  (bu yerda haqiqiy kalit turadi)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("GEMINI_API_KEY environment variable topilmadi yoki to'ldirilmagan!")

# v1 + gemini-2.0-flash
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"

app = FastAPI(title="Gemini Permit Navigation API (hints + multi-PDF)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # demo uchun ochiq
    allow_methods=["*"],
    allow_headers=["*"],
)


def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def build_google_maps_link(origin: str, destination: str) -> str:
    params = {"api": "1", "origin": origin, "destination": destination}
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


async def ask_gemini_with_pdfs_and_hints(
    start_address: str,
    end_address: str,
    permits: List[UploadFile],
) -> dict:
    # PDF -> inlineData (base64)
    inline_parts = []
    for permit in permits:
        content = await permit.read()
        if not content:
            continue
        inline_parts.append({
            "inlineData": {
                "data": pdf_to_base64(content),
                "mimeType": "application/pdf",
            }
        })

    # Agar PDF ham, hint ham yo'q bo'lsa – umuman ma'lumot yo'q
    if not inline_parts and not (start_address and end_address):
        raise HTTPException(
            400,
            "Hech bo'lmaganda 1 ta permit PDF yoki ikkala adresni to'liq kiriting.",
        )

    prompt = f"""
You are a senior logistics & dispatch assistant.

You receive multiple permit PDFs for a SINGLE load (rate confirmation, TX permit, CO permit, etc.).
Each PDF may contain:
- PU / PICKUP / ORIGIN info
- DEL / DELIVERY / DESTINATION info
- addresses, cities, states, dates, highways.

The user may also give optional hint addresses.

User hints:
- starting_address_hint: "{start_address or "[none]"}"
- destination_address_hint: "{end_address or "[none]"}"

Your tasks:
1) Read ALL PDFs together as ONE load (if any PDFs are attached).
2) Use the hints if they are useful, but the permits are the source of truth.
3) Decide final Google-Maps-friendly origin and destination:
   - city + state or full address that works well in Google Maps search.
   - If permits say things like "5.0mi SE of SH114 & FM 718"
     or "2.8mi from BOONE", convert them into the nearest town/city + state
     (e.g. "Rhome, TX" or "Boone, CO") instead of raw highway text.
4) If there are NO PDFs but user hints are present, just use the hints.

Return ONLY raw JSON in exactly this structure:

{{
  "origin": "<origin text for Google Maps>",
  "destination": "<destination text for Google Maps>",
  "notes": "short explanation of how you chose them"
}}

NO markdown.
NO code fences.
NO extra keys.
"""

    parts = [{"text": prompt}]
    parts.extend(inline_parts)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ]
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        raise HTTPException(500, f"Gemini error: {r.text}")

    try:
        resp_json = r.json()
        raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise HTTPException(500, f"Gemini javob formati noto'g'ri: {r.text}")

    text = raw_text.strip()

    # Agar baribir ```json ... ``` tashlab yuborsa – tozalaymiz
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Faqat { ... } orasini ajratib olamiz
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx + 1].strip()

    try:
        data = json.loads(text)
    except Exception:
        raise HTTPException(500, f"Gemini JSON formatida qaytarmadi: {text}")

    return data


@app.post("/api/generate-navigation-link")
async def generate(
    start_address: str = Form(""),
    end_address: str = Form(""),
    permits: List[UploadFile] = File(...),  # bitta input, ichiga 4–5 ta PDF
):
    # front orqali kamida 1 ta PDF talab qilamiz, lekin baribir chek:
    if not permits and not (start_address and end_address):
        raise HTTPException(
            400,
            "Hech bo'lmaganda 1 ta permit PDF yoki ikkala adresni to'liq kiriting.",
        )

    data = await ask_gemini_with_pdfs_and_hints(start_address, end_address, permits)

    origin = (data.get("origin") or start_address).strip()
    destination = (data.get("destination") or end_address).strip()
    notes = (data.get("notes") or "").strip()

    if not origin or not destination:
        raise HTTPException(500, f"Gemini pickup/delivery topa olmadi: {data}")

    link = build_google_maps_link(origin, destination)

    return {
        "success": True,
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "google_maps_link": link,
    }
