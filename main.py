# import os
# import json
# import base64
# from typing import List, Optional
# from urllib.parse import urlencode

# import httpx
# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv

# load_dotenv()

# # ========== GEMINI API KEY ==========

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     raise Exception("GEMINI_API_KEY environment variable is missing!")

# # v1 API + gemini-2.0-flash modeli
# GEMINI_API_URL = (
#     "https://generativelanguage.googleapis.com/v1/models/"
#     "gemini-2.0-flash:generateContent"
# )

# # ========== FASTAPI ==========

# app = FastAPI(title="Gemini (REST) Permit Navigation API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # ========== UTIL ==========

# def build_google_maps_link(origin: str, destination: str) -> str:
#     params = {"api": "1", "origin": origin, "destination": destination}
#     return f"https://www.google.com/maps/dir/?{urlencode(params)}"


# def pdf_to_base64(file_bytes: bytes) -> str:
#     return base64.b64encode(file_bytes).decode("utf-8")


# async def ask_gemini_with_pdfs(
#     start_address: str,
#     end_address: str,
#     permits: Optional[List[UploadFile]],
# ) -> dict:
#     """
#     Variantlar:
#     - Agar permits bo'lmasa → faqat user yozgan addresslardan foydalanamiz (Gemini yo'q).
#     - Agar permits bo'lsa → Gemini PDFlarni o'qib, origin/destination ni aniqlaydi.
#     """

#     permits = permits or []
#     start_address = (start_address or "").strip()
#     end_address = (end_address or "").strip()

#     # 1) Hech qanday PDF yo'q – faqat adres bilan ishlash
#     if not permits:
#         if not (start_address and end_address):
#             raise HTTPException(
#                 400,
#                 "Provide at least one permit PDF or both starting and destination addresses.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "No permits uploaded. Used user-provided addresses directly.",
#         }

#     # 2) PDFlar bor – Gemini bilan ishlaymiz
#     inline_parts = []
#     for permit in permits:
#         content = await permit.read()
#         if not content:
#             continue

#         inline_parts.append(
#             {
#                 "inlineData": {
#                     "data": pdf_to_base64(content),
#                     "mimeType": "application/pdf",
#                 }
#             }
#         )

#     if not inline_parts:
#         # Fayllar bo'sh bo'lsa ham fallback – faqat adreslardan foydalanamiz
#         if not (start_address and end_address):
#             raise HTTPException(
#                 400,
#                 "Permit files are empty and addresses are missing. "
#                 "Provide at least addresses or valid PDFs.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "Permit files were empty. Used user-provided addresses.",
#         }

#     # Gemini prompt – adreslar ham kontekst sifatida beriladi
#     prompt = f"""
# You are a senior logistics & dispatch assistant.

# You receive multiple permit PDF files (rate confirmation, TX PERMIT, CO PERMIT, etc.).
# Each permit may contain load info: PU (pickup), ORIGIN, PICKUP, DEL (delivery),
# DESTINATION, addresses, cities, and dates.

# User input (optional):
# - Starting address: "{start_address or "not provided"}"
# - Destination address: "{end_address or "not provided"}"

# Your task:
# 1) Read ALL PDFs together as ONE load.
# 2) Determine the pickup CITY/ADDRESS and STATE where the driver starts.
# 3) Determine the delivery CITY/ADDRESS and STATE where the driver finishes.
# 4) If only highway references like "5.0mi SE of SH114 & FM 718" or "2.8mi from BOONE"
#    are given, convert them into a nearest town/city + state (e.g. "Rhome, TX", "Boone, CO").
# 5) If the user-provided addresses look correct, you may keep them or slightly refine them.
# 6) Respond ONLY raw JSON:

# {{
#   "origin": "<Google Maps friendly query: city/state or address>",
#   "destination": "<Google Maps friendly query: city/state or address>",
#   "notes": "short explanation"
# }}

# No markdown. No extra keys.
# """

#     payload = {
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": [
#                     {"text": prompt},
#                     *inline_parts,
#                 ],
#             }
#         ]
#     }

#     url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

#     async with httpx.AsyncClient(timeout=60) as client:
#         r = await client.post(url, json=payload)

#     if r.status_code != 200:
#         raise HTTPException(500, f"Gemini error: {r.text}")

#     try:
#         resp_json = r.json()
#         raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
#     except Exception:
#         raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

#     # --- Cleanup: strip ```json ... ``` etc. ---
#     text = raw_text.strip()
#     if text.startswith("```"):
#         lines = text.splitlines()
#         if lines and lines[0].startswith("```"):
#             lines = lines[1:]
#         if lines and lines[-1].startswith("```"):
#             lines = lines[:-1]
#         text = "\n".join(lines).strip()

#     start = text.find("{")
#     end = text.rfind("}")
#     if start != -1 and end != -1:
#         text = text[start : end + 1].strip()

#     try:
#         data = json.loads(text)
#     except Exception:
#         raise HTTPException(500, f"Gemini did not return valid JSON: {text}")

#     return data


# # ========== API ROUTE ==========

# @app.post("/api/generate-navigation-link")
# async def generate(
#     start_address: str = Form(""),
#     end_address: str = Form(""),
#     permits: Optional[List[UploadFile]] = File(None),
# ):
#     """
#     Frontend yuboradigan forma:
#     - start_address (optional text)
#     - end_address (optional text)
#     - permits (0..N ta PDF)
#     """
#     data = await ask_gemini_with_pdfs(start_address, end_address, permits)

#     origin = (data.get("origin") or "").strip()
#     destination = (data.get("destination") or "").strip()
#     notes = (data.get("notes") or "").strip()

#     if not origin or not destination:
#         raise HTTPException(500, f"Could not determine origin/destination: {data}")

#     link = build_google_maps_link(origin, destination)

#     return {
#         "success": True,
#         "origin": origin,
#         "destination": destination,
#         "notes": notes,
#         "google_maps_link": link,
#     }


import os
import json
import base64
from typing import List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# --------- Gemini config ---------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = bool(GEMINI_API_KEY)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-2.0-flash:generateContent"
)

# --------- FastAPI app ---------

app = FastAPI(title="Permit Navigation Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # demo/prototype; prod-da domen bilan cheklasang bo'ladi
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utils ---------

def build_google_maps_link(origin: str, destination: str, travel_mode: str = "driving") -> str:
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


async def analyze_route_with_gemini(
    start_address: str,
    end_address: str,
    permits: Optional[List[UploadFile]],
) -> dict:
    """
    Logic:
    - If NO permits:
        - require both addresses
        - return them directly (no Gemini).
    - If permits exist:
        - if no Gemini key: fall back to addresses if possible.
        - else: call Gemini with PDFs + optional addresses.
    """

    permits = permits or []
    start_address = (start_address or "").strip()
    end_address = (end_address or "").strip()

    # 1) No permits at all => pure address mode
    if not permits:
        if not (start_address and end_address):
            raise HTTPException(
                400,
                "Please provide at least one permit PDF or both starting and destination addresses.",
            )

        return {
            "origin": start_address,
            "destination": end_address,
            "notes": "No permits uploaded. Used user-provided addresses directly.",
            "used_gemini": False,
        }

    # 2) Permits exist but Gemini is not configured
    if not HAS_GEMINI:
        if not (start_address and end_address):
            raise HTTPException(
                500,
                "Permits were uploaded but Gemini is not configured. "
                "Please either configure GEMINI_API_KEY or provide both addresses.",
            )

        return {
            "origin": start_address,
            "destination": end_address,
            "notes": "Permits uploaded but Gemini API key missing. Used user-provided addresses.",
            "used_gemini": False,
        }

    # 3) Permits exist and Gemini is available → call Gemini
    inline_parts = []
    for permit in permits:
        content = await permit.read()
        if not content:
            continue

        inline_parts.append(
            {
                "inlineData": {
                    "data": pdf_to_base64(content),
                    "mimeType": "application/pdf",
                }
            }
        )

    if not inline_parts:
        # All files were empty → fallback to addresses
        if not (start_address and end_address):
            raise HTTPException(
                400,
                "Permit files are empty and addresses are missing. "
                "Provide at least addresses or valid PDFs.",
            )

        return {
            "origin": start_address,
            "destination": end_address,
            "notes": "Permit files were empty. Used user-provided addresses.",
            "used_gemini": False,
        }

    prompt = f"""
You are a senior logistics & dispatch assistant.

You receive multiple permit PDF files (rate confirmation, TX PERMIT, CO PERMIT, etc.).
Each permit may contain load info: PU (pickup), ORIGIN, PICKUP, DEL (delivery),
DESTINATION, addresses, cities, and dates.

User input (optional):
- Starting address: "{start_address or "not provided"}"
- Destination address: "{end_address or "not provided"}"

Your task:
1) Read ALL PDFs together as ONE load.
2) Determine the pickup CITY/ADDRESS and STATE where the driver starts.
3) Determine the delivery CITY/ADDRESS and STATE where the driver finishes.
4) If only highway references like "5.0mi SE of SH114 & FM 718" or "2.8mi from BOONE"
   are given, convert them into a nearest town/city + state (e.g. "Rhome, TX", "Boone, CO").
5) If the user-provided addresses look correct, you may keep them or slightly refine them.
6) Respond ONLY raw JSON:

{{
  "origin": "<Google Maps friendly query: city/state or address>",
  "destination": "<Google Maps friendly query: city/state or address>",
  "notes": "short explanation"
}}

No markdown. No extra keys.
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    *inline_parts,
                ],
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
        raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

    # Clean possible ```json ... ``` wrappers
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1].strip()

    try:
        data = json.loads(text)
    except Exception:
        raise HTTPException(500, f"Gemini did not return valid JSON: {text}")

    origin = (data.get("origin") or start_address).strip()
    destination = (data.get("destination") or end_address).strip()
    notes = (data.get("notes") or "").strip() or "Origin/destination were determined from permits and user input."

    return {
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "used_gemini": True,
    }


# --------- API route ---------

@app.post("/api/generate-navigation-link")
async def generate_navigation_link(
    start_address: str = Form(""),
    end_address: str = Form(""),
    travel_mode: str = Form("driving"),
    permits: Optional[List[UploadFile]] = File(None),
):
    """
    Accepts:
    - start_address (optional)
    - end_address (optional)
    - travel_mode: driving|walking|bicycling|transit (default: driving)
    - permits: 0..N PDF files
    """

    # Normalize travel_mode
    allowed_modes = {"driving", "walking", "bicycling", "transit"}
    travel_mode = (travel_mode or "driving").lower()
    if travel_mode not in allowed_modes:
        travel_mode = "driving"

    data = await analyze_route_with_gemini(start_address, end_address, permits)

    origin = (data.get("origin") or "").strip()
    destination = (data.get("destination") or "").strip()
    notes = (data.get("notes") or "").strip()
    used_gemini = bool(data.get("used_gemini"))

    if not origin or not destination:
        raise HTTPException(500, f"Could not determine origin/destination: {data}")

    link = build_google_maps_link(origin, destination, travel_mode)

    return JSONResponse(
        {
            "success": True,
            "origin": origin,
            "destination": destination,
            "notes": notes,
            "google_maps_link": link,
            "travel_mode": travel_mode,
            "used_gemini": used_gemini,
        }
    )
