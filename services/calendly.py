import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from config.app_config import MODE_NLA

_SCHEDULING_PATTERNS = re.compile(
    r"\b(schedule|book|meeting|appointment|call|available|availability|calendly|slot|free time)\b",
    re.IGNORECASE,
)

BASE_URL = "https://api.calendly.com"


class CalendlyClient:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        self._user_uri = None
        self._timezone = None

    def _get(self, path, params=None):
        resp = self.session.get(f"{BASE_URL}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, json_data=None):
        resp = self.session.post(f"{BASE_URL}{path}", json=json_data)
        resp.raise_for_status()
        return resp.json()

    def get_current_user(self):
        data = self._get("/users/me")
        resource = data["resource"]
        self._user_uri = resource["uri"]
        self._timezone = resource["timezone"]
        return resource

    @property
    def user_uri(self):
        if not self._user_uri:
            self.get_current_user()
        return self._user_uri

    @property
    def timezone(self):
        if not self._timezone:
            self.get_current_user()
        return self._timezone

    def list_event_types(self):
        data = self._get("/event_types", params={
            "user": self.user_uri,
            "active": "true",
        })
        return [
            {
                "name": et["name"],
                "duration": et.get("duration"),
                "scheduling_url": et["scheduling_url"],
                "uri": et["uri"],
                "description": et.get("description_plain", ""),
            }
            for et in data.get("collection", [])
        ]

    def list_available_times(self, event_type_uri, days=7):
        now = datetime.now(ZoneInfo("UTC"))
        start = now.isoformat()
        end = (now + timedelta(days=days)).isoformat()
        data = self._get("/event_type_available_times", params={
            "event_type": event_type_uri,
            "start_time": start,
            "end_time": end,
        })
        return [
            {
                "start_time": slot["start_time"],
                "scheduling_url": slot.get("scheduling_url", ""),
            }
            for slot in data.get("collection", [])
            if slot.get("status") == "available"
        ]

    def create_invitee(self, event_type_uri, name, email):
        event_uuid = event_type_uri.rsplit("/", 1)[-1]
        data = self._post(f"/scheduled_events/{event_uuid}/invitees", json_data={
            "name": name,
            "email": email,
        })
        return data


def fetch_event_types(client):
    try:
        return client.list_event_types()
    except Exception:
        return []


def fetch_available_slots(client, event_type_uri):
    try:
        raw_slots = client.list_available_times(event_type_uri=event_type_uri)
    except Exception:
        return {}

    grouped = defaultdict(list)
    for slot in raw_slots:
        dt = datetime.fromisoformat(slot["start_time"])
        date_key = dt.strftime("%Y-%m-%d")
        grouped[date_key].append(slot)
    return dict(grouped)


def format_slot_time(iso_time, timezone="America/Chicago"):
    dt = datetime.fromisoformat(iso_time)
    tz = ZoneInfo(timezone)
    localized = dt.astimezone(tz)
    tz_abbr = localized.strftime("%Z")
    return localized.strftime(f"%I:%M %p {tz_abbr}")


def get_booking_url(event_type):
    return event_type["scheduling_url"]


def detect_scheduling_intent(message):
    return bool(_SCHEDULING_PATTERNS.search(message))


def create_booking(client, event_type_uri, name, email):
    try:
        response = client.create_invitee(
            event_type_uri=event_type_uri,
            name=name,
            email=email,
        )
        resource = response["resource"]
        return {
            "name": resource["name"],
            "email": resource["email"],
            "event": resource.get("event"),
        }
    except Exception:
        return None


def is_booking_supported(agent_mode):
    return agent_mode != MODE_NLA


_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def validate_email(email: str) -> bool:
    return bool(_EMAIL_RE.fullmatch(email.strip())) if email else False


def extract_booking_info(client, model_id: str, message: str) -> tuple[dict, int]:
    """
    Use the LLM to pull name, email, and preferred time from a natural-language message.
    Returns ({"name": str|None, "email": str|None, "preferred_time": str|None}, token_count).
    """
    from google import genai

    prompt = (
        'Extract scheduling details from the message below.\n'
        'Return ONLY a JSON object with keys "name", "email", "preferred_time".\n'
        'Set a key to null if the info is absent.\n\n'
        'Examples:\n'
        '- "I\'m Jane Doe, jane@example.com, free Thursday 2pm" → '
        '{"name":"Jane Doe","email":"jane@example.com","preferred_time":"Thursday 2pm"}\n'
        '- "schedule a call" → {"name":null,"email":null,"preferred_time":null}\n'
        '- "Ryan here, ryan@test.com" → {"name":"Ryan","email":"ryan@test.com","preferred_time":null}\n\n'
        f'Message: "{message}"\n\n'
        "Return ONLY the JSON object."
    )
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0, max_output_tokens=150),
        )
        text = response.text or ""
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(text[start : end + 1])
            tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0
            return {
                "name": data.get("name") or None,
                "email": data.get("email") or None,
                "preferred_time": data.get("preferred_time") or None,
            }, tokens
    except Exception:
        pass
    return {"name": None, "email": None, "preferred_time": None}, 0


_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

_HOUR_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)
_DAY_RE = re.compile(r"\b(\d{1,2})\b")


def _direct_match(preferred_time, flat_slots):
    """Try deterministic matching before LLM fallback."""
    pref = preferred_time.lower().strip()

    # --- Exact / substring match (user picked from the suggested list) ---
    for slot in flat_slots:
        label = f"{slot['date']} {slot['time_label']}".lower()
        clean_pref = pref.replace("**", "").replace(" at ", " ")
        if clean_pref == label or label in pref or pref in label:
            return slot

    # --- Fuzzy component match ("9am Monday June 15" → 2026-06-15 09:00 AM) ---
    # Extract month
    matched_month = None
    for name, num in _MONTH_MAP.items():
        if name in pref:
            matched_month = num
            break

    # Extract hour + am/pm
    hour_match = _HOUR_RE.search(pref)
    matched_hour = None
    matched_minute = "00"
    if hour_match:
        h = int(hour_match.group(1))
        matched_minute = hour_match.group(2) or "00"
        is_pm = hour_match.group(3).lower() == "pm"
        if is_pm and h != 12:
            h += 12
        elif not is_pm and h == 12:
            h = 0
        matched_hour = f"{h:02d}"

    # Extract day number (skip the hour we already matched)
    matched_day = None
    if matched_month:
        remaining = pref
        if hour_match:
            remaining = pref[:hour_match.start()] + pref[hour_match.end():]
        day_candidates = _DAY_RE.findall(remaining)
        for d in day_candidates:
            if 1 <= int(d) <= 31:
                matched_day = f"{int(d):02d}"
                break

    if matched_month and matched_day and matched_hour:
        target_date = f"-{matched_month}-{matched_day}"
        target_time = f"{matched_hour}:{matched_minute}"
        for slot in flat_slots:
            if target_date in slot["date"] and target_time in slot["start_time"]:
                return slot

    if matched_month and matched_day:
        target_date = f"-{matched_month}-{matched_day}"
        candidates = [s for s in flat_slots if target_date in s["date"]]
        if len(candidates) == 1:
            return candidates[0]
        if matched_hour and candidates:
            target_time = f"{matched_hour}:{matched_minute}"
            for s in candidates:
                if target_time in s["start_time"]:
                    return s

    return None


def pick_best_slot(
    client,
    model_id: str,
    preferred_time: str,
    slots_by_date: dict,
    timezone: str = "America/Chicago",
) -> tuple[dict | None, int]:
    """
    Given a natural-language preferred time string and the grouped slots dict,
    return the best-matching slot (or None if nothing fits) and token count.
    """
    from google import genai

    flat = []
    for date_key in sorted(slots_by_date):
        for slot in slots_by_date[date_key]:
            flat.append(
                {
                    "date": date_key,
                    "time_label": format_slot_time(slot["start_time"], timezone=timezone),
                    "start_time": slot["start_time"],
                    "scheduling_url": slot.get("scheduling_url", ""),
                }
            )

    if not flat:
        return None, 0

    direct = _direct_match(preferred_time, flat)
    if direct:
        return direct, 0

    slot_lines = []
    for i, s in enumerate(flat):
        dt = datetime.fromisoformat(s["start_time"])
        day_name = dt.strftime("%A")
        slot_lines.append(f"{i + 1}. {day_name} {s['date']} {s['time_label']}")
    slots_text = "\n".join(slot_lines)

    today = datetime.now().strftime("%A %Y-%m-%d")
    prompt = (
        f"Today is {today}.\n"
        f'The user wants to meet at: "{preferred_time}"\n\n'
        f"Available slots:\n{slots_text}\n\n"
        "Which slot number best matches? Reply with ONLY the number. "
        "If none match reasonably, reply with 0."
    )
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0, max_output_tokens=10),
        )
        tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0
        text = (response.text or "0").strip()
        # Extract first number from response in case LLM adds extra text
        match = re.search(r"\d+", text)
        idx = (int(match.group()) - 1) if match else -1
        if 0 <= idx < len(flat):
            return flat[idx], tokens
        return None, tokens
    except Exception:
        return None, 0
