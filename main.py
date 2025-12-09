import os
import json
import base64
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

# --------- mini config ---------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HAS_GEMINI = bool(GEMINI_API_KEY)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1/models/"
    "gemini-2.0-flash:generateContent"
)

# --------- Google Maps Embed config (faqat backendda saqlanadi) ---------

GOOGLE_MAPS_EMBED_API_KEY = os.getenv("MAPS_API_KEY")
HAS_EMBED_KEY = bool(GOOGLE_MAPS_EMBED_API_KEY)

# --------- FastAPI app ---------

app = FastAPI(title="Permit Navigation Link API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # demo/prototype; prod-da domen bilan cheklash mumkin
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utils ---------

def pdf_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


def _normalize_waypoints_for_directions(
    waypoints: Optional[List[str]],
    add_via_prefix: bool = True,
    max_points: int = 20,
) -> List[str]:
    """
    Waypointlarni tozalash:
    - bo'shlarini tashlab yuboradi
    - takrorlarini olib tashlaydi
    - kerak bo'lsa boshiga 'via:' qo'shib qo'yadi (Directions URL uchun)
    """
    if not waypoints:
        return []

    cleaned: List[str] = []
    seen = set()

    for w in waypoints:
        if not w:
            continue
        w = w.strip()
        if not w:
            continue

        if add_via_prefix:
            if not w.lower().startswith("via:"):
                w = f"via:{w}"

        key = w.lower()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(w)

        if len(cleaned) >= max_points:
            break

    return cleaned


def build_google_maps_link(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> str:
    """
    Google Maps Directions URL (foydalanuvchi bosadigan link).
    - origin / destination – matn
    - waypoints – "via:...." ko‘rinishidagi ro‘yxat (max ~20 ta)
    """
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }

    cleaned = _normalize_waypoints_for_directions(
        waypoints,
        add_via_prefix=True,
        max_points=20,
    )
    if cleaned:
        # `via:...|via:...` ko‘rinishidagi qator
        params["waypoints"] = "|".join(cleaned)

    # safe="|:" – via: va | belgilarini URL-encoding qilmaslik uchun
    return f"https://www.google.com/maps/dir/?{urlencode(params, safe='|:')}"


def build_google_maps_embed_url(
    origin: str,
    destination: str,
    travel_mode: str = "driving",
    waypoints: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Google Maps Embed API (iframe uchun) Directions URL.
    Bu yerda API KEY ishlatiladi va faqat backendda qoladi.
    Frontend faqat `map_embed_url` ni oladi.
    """
    if not HAS_EMBED_KEY:
        return None

    params: Dict[str, Any] = {
        "key": GOOGLE_MAPS_EMBED_API_KEY,
        "origin": origin,
        "destination": destination,
        "mode": travel_mode,
    }

    # Embed Directions API uchun via: shart emas, shunchaki waypointlar yetarli
    cleaned = _normalize_waypoints_for_directions(
        waypoints,
        add_via_prefix=False,  # bu yerda "via:" qo‘shmaymiz
        max_points=20,
    )
    if cleaned:
        # "Wichita Falls, TX|Childress, TX|..." kabi
        params["waypoints"] = "|".join(cleaned)

    # `|` belgisi saqlanib qolishi uchun safe="|"
    return f"https://www.google.com/maps/embed/v1/directions?{urlencode(params, safe='|')}"


async def analyze_route_with_gemini(
    start_address: str,
    end_address: str,
    permits: Optional[List[UploadFile]],
) -> Dict[str, Any]:
    """
    Logika:
    - Agar permits yo‘q:
        - ikkala address ham bo‘lishi shart
        - Gemini chaqirilmaydi.
    - Agar permits mavjud:
        - Gemini yo‘q bo‘lsa (API key bo‘lmasa) -> faqat addresslardan foydalanamiz.
        - Aks holda:
            - 15–20 ta permit PDF (multi-state, multi-segment) ni o‘qib:
              origin / destination / waypoints / segments ni chiqaradi.
    """

    permits = permits or []
    start_address = (start_address or "").strip()
    end_address = (end_address or "").strip()

    # 1) Umuman permit yo‘q → to‘g‘ridan-to‘g‘ri address rejimi
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
            "segments": [],
        }

    # 2) Permits bor, lekin GEMINI yo‘q
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
            "segments": [],
        }

    # 3) Permits + GEMINI → to‘liq AI tahlil
    parts: List[dict] = []
    any_pdf = False

    # 🔥 Prompt – ROUTE + MILES + ketma-ketlik + to‘liq segmentlar
    prompt = f"""
You are a senior logistics & dispatch assistant.

You receive up to ~20 permit PDF files (TX PERMIT, CO PERMIT, Rate Confirm, etc.)
for ONE oversize/overweight load. Each permit describes ROUTE + MILES that the
truck is ALLOWED to travel inside that jurisdiction.

User high-level input (optional):
- Global starting address A1: "{start_address or "not provided"}"
- Global final destination A2: "{end_address or "not provided"}"

CRITICAL REQUIREMENTS (read carefully):

1) You MUST work from the PERMIT TEXT – ROUTE and MILES – not from your own idea
   of a shortcut. Do NOT simplify or optimize the route.
   - If the permit says: "US287 W → IH44 E → Exit 3A → US-287 N → ...", then your
     route MUST follow exactly these highways and junctions in the correct order.
   - The goal is to MATCH the permit's legal route, not the shortest one.

2) Build a single continuous route from A1 to A2 by stitching ALL relevant permits
   in order (e.g., TX → OK → CO). Ignore any permit that clearly belongs to a
   different, unrelated load.

3) For every segment, use the ROUTE and MILES lines to reconstruct the sequence:
   Example skeleton:
   - state: "TX"
     route: "US287 W"
     from: "US287 W [US81] [SH114] (RHOME TX)"
     to:   "IH44 E [US277] [US281] [CENTRAL FREEWAY]"
     miles: 90.0

4) When the permit describes locations like:
   - "5.0mi SE of SH114 & FM 718"
   - "2.8mi from BOONE"
   you MUST approximate them to a nearby Google Maps-friendly query, e.g.:
   - "US-287 & SH-114 near Rhome, TX"
   - "CO-96 near Boone, CO"

5) OUTPUT FORMAT — IMPORTANT:
   Return ONLY one JSON object, no markdown, no comments. It must be valid JSON:

   {{
     "origin": "<Google Maps friendly origin>",
     "destination": "<Google Maps friendly destination>",
     "notes": "short explanation of how you stitched the route from the permits",
     "waypoints": [
       "<short gmaps query for a junction/exit on the route in correct order>",
       "... up to about 15–20 items max ..."
     ],
     "segments": [
       {{
         "order": 1,
         "state": "TX",
         "route": "US287 W",
         "from": "<from description from permit>",
         "to": "<to description from permit>",
         "miles": 90.0,
         "gmaps_query": "<short gmaps query near this segment>"
       }},
       {{
         "order": 2,
         "state": "TX",
         "route": "IH44 E",
         "from": "...",
         "to": "...",
         "miles": 2.4,
         "gmaps_query": "IH-44 E near Wichita Falls, TX"
       }}
       // additional segments in strict travel order...
     ]
   }}

   - "origin" should be the FIRST pickup / start city of the full trip, aligned
     with A1 if A1 is reasonable.
   - "destination" should be the FINAL delivery / end city of the full trip,
     aligned with A2 if A2 is reasonable.
   - "waypoints" must be in the correct travel order and represent key exits /
     junctions / towns taken from the segments.
   - "segments" must reflect the PERMIT's legal route in the correct order
     including ROUTE + FROM + TO + MILES.

6) The JSON MUST be syntactically valid:
   - Use double quotes for keys and strings.
   - No trailing commas.
   - No comments.
   - No ``` fences.
"""

    parts.append({"text": prompt})

    # Har bir permit faylini qo‘shamiz
    for idx, permit in enumerate(permits, start=1):
        content = await permit.read()
        if not content:
            continue

        any_pdf = True

        if permit.filename:
            parts.append({"text": f"FILE_{idx} name: {permit.filename}"})

        parts.append(
            {
                "inlineData": {
                    "data": pdf_to_base64(content),
                    "mimeType": "application/pdf",
                }
            }
        )

    if not any_pdf:
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
            "segments": [],
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

    # ```json ... ``` bo‘lsa, tozalab olamiz
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
    except Exception as e:
        raise HTTPException(
            500,
            f"Gemini did not return valid JSON: {e}. Raw text: {text}",
        )

    origin = (data.get("origin") or start_address).strip()
    destination = (data.get("destination") or end_address).strip()
    notes = (data.get("notes") or "").strip() or \
        "Origin/destination were determined from permits (ROUTE+MILES) and user input."

    waypoints = data.get("waypoints") or []
    if not isinstance(waypoints, list):
        waypoints = []

    segments = data.get("segments") or []
    if not isinstance(segments, list):
        segments = []

    # Agar waypoints bo‘sh bo‘lsa, segmentlardan yig‘ib olamiz
    if not waypoints and segments:
        try:
            segments_sorted = sorted(
                segments,
                key=lambda s: s.get("order", 0)
            )
        except Exception:
            segments_sorted = segments

        tmp: List[str] = []
        for seg in segments_sorted:
            q = (seg.get("gmaps_query") or "").strip()
            if q:
                tmp.append(q)
        waypoints = tmp

    return {
        "origin": origin,
        "destination": destination,
        "notes": notes,
        "used_gemini": True,
        "waypoints": waypoints,
        "segments": segments,
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
    segments = data.get("segments") or []

    if not origin or not destination:
        raise HTTPException(500, f"Could not determine origin/destination: {data}")

    # Foydalanuvchi bosadigan classic directions link
    link = build_google_maps_link(origin, destination, travel_mode, waypoints)

    # iframe uchun Embed API URL (agar kalit bo'lsa)
    embed_url = build_google_maps_embed_url(origin, destination, travel_mode, waypoints)

    return JSONResponse(
        {
            "success": True,
            "origin": origin,
            "destination": destination,
            "notes": notes,
            "google_maps_link": link,
            "map_embed_url": embed_url,  # 🔥 frontend shu bilan ishlaydi
            "travel_mode": travel_mode,
            "used_gemini": used_gemini,
            "waypoints": waypoints,
            "segments": segments,
        }
    )


GOOGLE_MAPS_JS_API_KEY = os.getenv("MAPS_API_KEY")

@app.get("/api/config")
def get_config():
    return {
        "google_maps_js_api_key": GOOGLE_MAPS_JS_API_KEY
    }