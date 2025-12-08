import os
import json
import base64
from typing import List
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# ========== GEMINI API KEY ==========

# .env ichida:
# GEMINI_API_KEY=bu_yerga_haqiqiy_kalitingni_qoyasan
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("GEMINI_API_KEY environment variable topilmadi yoki to'ldirilmagan!")

# v1 API + gemini-2.0-flash modeli
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"


# ========== FASTAPI ==========

app = FastAPI(title="Gemini (REST) Permit Navigation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== UTIL ==========

def build_google_maps_link(origin: str, destination: str) -> str:
    params = {"api": "1", "origin": origin, "destination": destination}
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


async def ask_gemini_with_pdfs(permits: List[UploadFile]) -> dict:
    """
    Gemini 2.0 Flash modeliga:
    - prompt
    - PDF fayllar (base64)
    yuboriladi.
    U esa pickup/delivery ni JSON qilib qaytaradi.
    """

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

    if not inline_parts:
        raise HTTPException(400, "PDF fayllardan kontent olinmadi")

    # Gemini uchun prompt
    prompt = """
You are a senior logistics & dispatch assistant.

You receive multiple PDF permit files (rate confirmation and state permits).
Each permit may contain load info: PU (pickup), ORIGIN, PICKUP, DEL (delivery), DESTINATION,
addresses, cities, and dates.

Your task:
1) Read ALL PDFs together as ONE load.
2) Identify the pickup CITY/ADDRESS AND STATE where the driver starts (for Google Maps).
3) Identify the delivery CITY/ADDRESS AND STATE where the driver finishes (for Google Maps).
4) If the permit only gives highway references like "5.0mi SE of SH114 & FM 718"
   or "2.8mi from BOONE", then:
   - convert them to a nearest town/city + state name (for example: "Rhome, TX" or "Boone, CO")
   instead of returning the raw highway description.
5) Respond ONLY raw JSON:

{
  "origin": "<Google Maps friendly query: city/state or address>",
  "destination": "<Google Maps friendly query: city/state or address>",
  "notes": "short explanation"
}

No markdown, no extra keys, no highway engineering text in origin/destination.
"""


    # ⚠️ E’tibor: faqat contents + role, generationConfig ichida responseMimeType YO‘Q
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    *inline_parts
                ],
            }
        ]
        # Agar xohlasang, bu yerga faqat ruxsat etilgan fieldlarni qo‘yishing mumkin:
        # "generationConfig": {
        #     "temperature": 0.2,
        #     "maxOutputTokens": 512
        # }
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

    # 🔧 Yangi: markdown code block va keraksiz qismlarni tozalash
    text = raw_text.strip()

    # Agar ``` bilan boshlangan bo'lsa, birinchi va oxirgi qatorni olib tashlaymiz
    if text.startswith("```"):
        lines = text.splitlines()
        # birinchi qatorda ``` yoki ```json bo'ladi
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # oxirgi qatorda ham ``` bo'lishi mumkin
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Hali ham atrofida keraksiz gaplar bo'lsa,
    # faqat { ... } orasidagi JSON qismini ajratib olamiz
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1].strip()

    try:
        data = json.loads(text)
    except Exception:
        raise HTTPException(500, f"Gemini JSON formatida qaytarmadi: {text}")

    return data



# ========== API ROUTE ==========

@app.post("/api/generate-navigation-link")
async def generate(permits: List[UploadFile] = File(...)):
    if not permits:
        raise HTTPException(400, "Hech bo‘lmaganda 1 ta PDF yuborilsin")

    data = await ask_gemini_with_pdfs(permits)

    origin = data.get("origin", "").strip()
    destination = data.get("destination", "").strip()
    notes = data.get("notes", "").strip()

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
