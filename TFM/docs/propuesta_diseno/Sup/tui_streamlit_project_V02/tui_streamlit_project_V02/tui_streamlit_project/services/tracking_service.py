from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from database.repositories import TrackingRepository

_repo = TrackingRepository()


def create_session(user_id=None, source="direct", medium=None, campaign=None, device=None, country=None, session_id=None) -> str:
    sid = session_id or str(uuid.uuid4())
    _repo.create_session({
        "session_id": sid, "user_id": user_id, "source": source, "medium": medium,
        "campaign": campaign, "device": device, "country": country,
    })
    return sid


def register_event(session_id: str, event_type: str, page: str, element_id=None, product_id=None,
                   destination=None, user_id=None, source=None, medium=None, campaign=None,
                   device=None, country=None, response_time_ms=None, metadata: dict[str, Any] | None = None,
                   dedupe_key: str | None = None) -> bool:
    if dedupe_key is not None:
        dedupe_key = hashlib.sha1(f"{session_id}|{dedupe_key}".encode()).hexdigest()
    row = {
        "event_id": str(uuid.uuid4()), "session_id": session_id, "user_id": user_id,
        "page": page, "event_type": event_type, "element_id": element_id, "product_id": product_id,
        "destination": destination, "source": source, "medium": medium, "campaign": campaign,
        "device": device, "country": country, "response_time_ms": response_time_ms,
        "metadata": json.dumps(metadata or {}, ensure_ascii=False, default=str), "dedupe_key": dedupe_key,
    }
    return _repo.insert_event(row)
