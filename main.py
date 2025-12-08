# import os
# import json
# import base64
# from typing import List, Optional
# from urllib.parse import urlencode

# import httpx
# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv

# load_dotenv()

# # --------- Gemini config ---------

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# HAS_GEMINI = bool(GEMINI_API_KEY)

# GEMINI_API_URL = (
#     "https://generativelanguage.googleapis.com/v1/models/"
#     "gemini-2.0-flash:generateContent"
# )

# # --------- FastAPI app ---------

# app = FastAPI(title="Permit Navigation Link API")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],      # demo/prototype; prod-da domen bilan cheklasang bo'ladi
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# # --------- Utils ---------

# def build_google_maps_link(origin: str, destination: str, travel_mode: str = "driving") -> str:
#     params = {
#         "api": "1",
#         "origin": origin,
#         "destination": destination,
#         "travelmode": travel_mode,
#     }
#     return f"https://www.google.com/maps/dir/?{urlencode(params)}"


# def pdf_to_base64(file_bytes: bytes) -> str:
#     return base64.b64encode(file_bytes).decode("utf-8")


# async def analyze_route_with_gemini(
#     start_address: str,
#     end_address: str,
#     permits: Optional[List[UploadFile]],
# ) -> dict:
#     """
#     Logic:
#     - If NO permits:
#         - require both addresses
#         - return them directly (no Gemini).
#     - If permits exist:
#         - if no Gemini key: fall back to addresses if possible.
#         - else: call Gemini with PDFs + optional addresses.
#     """

#     permits = permits or []
#     start_address = (start_address or "").strip()
#     end_address = (end_address or "").strip()

#     # 1) No permits at all => pure address mode
#     if not permits:
#         if not (start_address and end_address):
#             raise HTTPException(
#                 400,
#                 "Please provide at least one permit PDF or both starting and destination addresses.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "No permits uploaded. Used user-provided addresses directly.",
#             "used_gemini": False,
#         }

#     # 2) Permits exist but Gemini is not configured
#     if not HAS_GEMINI:
#         if not (start_address and end_address):
#             raise HTTPException(
#                 500,
#                 "Permits were uploaded but Gemini is not configured. "
#                 "Please either configure GEMINI_API_KEY or provide both addresses.",
#             )

#         return {
#             "origin": start_address,
#             "destination": end_address,
#             "notes": "Permits uploaded but Gemini API key missing. Used user-provided addresses.",
#             "used_gemini": False,
#         }

#     # 3) Permits exist and Gemini is available → call Gemini
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
#         # All files were empty → fallback to addresses
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
#             "used_gemini": False,
#         }

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

#     # Clean possible ```json ... ``` wrappers
#     text = raw_text.strip()
#     if text.startswith("```"):
#         lines = text.splitlines()
#         if lines and lines[0].startswith("```"):
#             lines = lines[1:]
#         if lines and lines[-1].startswith("```"):
#             lines = lines[:-1]
#         text = "\n".join(lines).strip()

#     start_idx = text.find("{")
#     end_idx = text.rfind("}")
#     if start_idx != -1 and end_idx != -1:
#         text = text[start_idx : end_idx + 1].strip()

#     try:
#         data = json.loads(text)
#     except Exception:
#         raise HTTPException(500, f"Gemini did not return valid JSON: {text}")

#     origin = (data.get("origin") or start_address).strip()
#     destination = (data.get("destination") or end_address).strip()
#     notes = (data.get("notes") or "").strip() or "Origin/destination were determined from permits and user input."

#     return {
#         "origin": origin,
#         "destination": destination,
#         "notes": notes,
#         "used_gemini": True,
#     }


# # --------- API route ---------

# @app.post("/api/generate-navigation-link")
# async def generate_navigation_link(
#     start_address: str = Form(""),
#     end_address: str = Form(""),
#     travel_mode: str = Form("driving"),
#     permits: Optional[List[UploadFile]] = File(None),
# ):
#     """
#     Accepts:
#     - start_address (optional)
#     - end_address (optional)
#     - travel_mode: driving|walking|bicycling|transit (default: driving)
#     - permits: 0..N PDF files
#     """

#     # Normalize travel_mode
#     allowed_modes = {"driving", "walking", "bicycling", "transit"}
#     travel_mode = (travel_mode or "driving").lower()
#     if travel_mode not in allowed_modes:
#         travel_mode = "driving"

#     data = await analyze_route_with_gemini(start_address, end_address, permits)

#     origin = (data.get("origin") or "").strip()
#     destination = (data.get("destination") or "").strip()
#     notes = (data.get("notes") or "").strip()
#     used_gemini = bool(data.get("used_gemini"))

#     if not origin or not destination:
#         raise HTTPException(500, f"Could not determine origin/destination: {data}")

#     link = build_google_maps_link(origin, destination, travel_mode)

#     return JSONResponse(
#         {
#             "success": True,
#             "origin": origin,
#             "destination": destination,
#             "notes": notes,
#             "google_maps_link": link,
#             "travel_mode": travel_mode,
#             "used_gemini": used_gemini,
#         }
#     )

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
    allow_origins=["*"],  # demo/prototype; prod-da domen bilan cheklash mumkin
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utils ---------

def build_google_maps_link(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> str:
    """
    origin, destination, travel mode va ixtiyoriy waypointlar asosida
    Google Maps Directions URL yasaydi.
    """
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }

    if waypoints:
        # "City1|City2|City3" formatida
        clean = [w.strip() for w in waypoints if str(w).strip()]
        if clean:
            params["waypoints"] = "|".join(clean)

    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


# --------- Core logic ---------

async def analyze_route_with_gemini(
    start_address: str,
    end_address: str,
    permits: Optional[List[UploadFile]],
) -> dict:
    """
    Advanced logika:
    - 0 ta permit bo'lsa:
        - ikkala address bo'lishi shart, LLM ishlatilmaydi.
    - 1+ permit bo'lsa (15–20 ta gacha):
        - Agar GEMINI yo'q bo'lsa: address bo'lsa, bevosita o'shani ishlatamiz.
        - Agar GEMINI bor bo'lsa:
            -> semua permitlarni, ichidagi ROUTE/MILES jadvalini,
               PU/DEL/ORIGIN/DESTINATION ma'lumotlarini o'qib,
               aqlli tarzda global origin/destination va waypoints topadi.
    """

    permits = permits or []
    start_address = (start_address or "").strip()
    end_address = (end_address or "").strip()

    # 1) Hech qanday permit bo'lmasa — faqat address rejimi
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
            "waypoints": [],
        }

    # 2) Permits bor, lekin Gemini yo'q
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
            "waypoints": [],
        }

    # 3) Permits bor va Gemini mavjud → LLM orqali analiz
    parts: List[dict] = []

    # ---- Prompt: dynamic, route + miles aware, multi-leg + ordering ----
    prompt = f"""
You are an expert logistics and dispatch assistant.

You are given multiple permit PDF files for one (usually multi-state) load.
Each permit typically contains:

- HEADER / load info (carrier, shipper, load #, dates)
- ORIGIN / PICKUP / SHIP FROM sections
- DESTINATION / DELIVERY / SHIP TO sections
- ROUTE sections that describe highways and junctions
- MILES or distance tables, sometimes per segment

User input (optional, high-level hint):
- Global starting address A1: "{start_address or "not provided"}"
- Global final destination A2: "{end_address or "not provided"}"

Important:
- The uploaded permits can be 2–20 files for one route across several states
  (e.g., TX → OK → KS → CO etc.).
- Some files may be rate confirmations, some state permits, some pure route/mileage tables.

Your job is to reconstruct the REALISTIC over-the-road route for the driver.

Reasoning rules (very important):
1) Treat all permits as candidates for legs of ONE main trip.
   - Identify which permits clearly belong to the same load.
   - If a file looks totally unrelated (different states and directions, different load #),
     IGNORE it or mention it only in your internal reasoning (do not use it for the route).
2) Use all available details:
   - City + state names (Rhome, TX; Amarillo, TX; Stratford, OK; Campo, CO; Boone, CO, etc.)
   - Highway names (US-287, US-385, SH-114, CO-96, etc.)
   - ROUTE and MILES columns or tables.
   - Junction references like "x.y mi SE of SH114 & FM 718".
3) Use miles/distance info to keep the route consistent:
   - If the permit lists multiple segments with MILES, reconstruct a path where
     the total distance approximately matches those segment sums.
   - Prefer a sequence of cities and junctions that follow the same highways
     and general direction (e.g., south→north, east→west) without illogical jumps.
4) Global ORIGIN:
   - The earliest logical pick-up city/state in the chain.
   - If A1 (user start address) is close to that city, you can keep the city/state as the origin.
5) Global DESTINATION:
   - The final logical delivery city/state in the chain.
   - If A2 (user destination) is close to that city, you can keep the city/state as the destination.
6) Waypoints:
   - Choose 4–12 key cities or highway junction areas along the route to represent the path.
   - These must lie realistically on the corridor between ORIGIN and DESTINATION.
   - Do NOT invent random cities far away from the described highways.
   - Make them Google Maps friendly: "City, ST" or "City, State".
7) Everything must be derived dynamically from THESE permits + general US geography.
   - Do not rely on hardcoded examples.
   - If there is ambiguity, choose the route that best matches the ROUTE + MILES data.

Return ONLY valid JSON in this exact schema:

{{
  "origin": "<Google Maps friendly query: city/state or full address>",
  "destination": "<Google Maps friendly query: city/state or full address>",
  "waypoints": [
    "City1, ST",
    "City2, ST"
  ],
  "notes": "short explanation of how you chose the origin, destination and waypoints, including mention of key routes and miles."
}}

- No markdown.
- No extra top-level keys.
- No commentary outside JSON.
"""

    parts.append({"text": prompt})

    # Har bir fayl uchun: filename + inlineData (PDF)
    any_pdf = False
    max_files = 25  # tokenlarni haddan oshirmaslik uchun limit

    for idx, permit in enumerate(permits[:max_files], start=1):
        content = await permit.read()
        if not content:
            continue

        any_pdf = True

        filename = permit.filename or f"permit_{idx}.pdf"
        parts.append({"text": f"FILE_{idx} NAME: {filename}"})
        parts.append(
            {
                "inlineData": {
                    "data": pdf_to_base64(content),
                    "mimeType": "application/pdf",
                }
            }
        )

    if not any_pdf:
        # Fayllar bo'sh bo'lib chiqqan holat
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
            "waypoints": [],
        }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ]
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload)

    if r.status_code != 200:
        raise HTTPException(500, f"Gemini error: {r.text}")

    try:
        resp_json = r.json()
        raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise HTTPException(500, f"Gemini response format is invalid: {r.text}")

    # --- Clean possible ```json ... ``` wrappers ---
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
    notes = (data.get("notes") or "").strip() or (
        "Origin/destination and waypoints were determined from permits (routes + miles) and user input."
    )

    raw_waypoints = data.get("waypoints") or []
    waypoints: List[str] = []
    if isinstance(raw_waypoints, list):
        for w in raw_waypoints:
            s = str(w).strip()
            if s:
                waypoints.append(s)

    return {
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "used_gemini": True,
        "waypoints": waypoints,
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
    - permits: 0..N PDF files (15–20+ segments supported)
    """

    allowed_modes = {"driving", "walking", "bicycling", "transit"}
    travel_mode = (travel_mode or "driving").lower()
    if travel_mode not in allowed_modes:
        travel_mode = "driving"

    data = await analyze_route_with_gemini(start_address, end_address, permits)

    origin = (data.get("origin") or "").strip()
    destination = (data.get("destination") or "").strip()
    notes = (data.get("notes") or "").strip()
    used_gemini = bool(data.get("used_gemini"))
    waypoints = data.get("waypoints") or []

    if not origin or not destination:
        raise HTTPException(500, f"Could not determine origin/destination: {data}")

    link = build_google_maps_link(origin, destination, travel_mode, waypoints)

    return JSONResponse(
        {
            "success": True,
            "origin": origin,
            "destination": destination,
            "notes": notes,
            "google_maps_link": link,
            "travel_mode": travel_mode,
            "used_gemini": used_gemini,
            "waypoints": waypoints,
        }
    )

