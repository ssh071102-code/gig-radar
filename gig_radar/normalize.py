import hashlib
from datetime import UTC, datetime

from gig_radar.models import Lead, RawItem


def lead_id(source: str, external_id: str) -> str:
    h = hashlib.sha1(f"{source}:{external_id}".encode()).hexdigest()[:16]
    return f"{source}:{h}"


def raw_to_lead(raw: RawItem) -> Lead:
    return Lead(
        id=lead_id(raw.source, raw.external_id),
        source=raw.source,
        url=raw.url,
        title=raw.title,
        raw_text=raw.raw_text,
        posted_at=raw.posted_at,
        fetched_at=datetime.now(UTC),
        client_handle=raw.client_handle,
    )
