from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

Source = Literal["reddit", "rss", "upwork", "x"]
Category = Literal["ai-integration", "ai-video", "automation", "other"]
ChannelAction = Literal["comment", "email", "dm", "upwork_manual"]
Status = Literal["new", "scored", "unscored", "pushed", "applied", "skipped", "won"]


class RawItem(BaseModel):
    source: Source
    external_id: str            # stable id within the source (post id / guid)
    url: str
    title: str
    raw_text: str
    posted_at: Optional[datetime] = None
    client_handle: Optional[str] = None


class Lead(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str                     # stable hash: source + external_id
    source: Source
    url: str
    title: str
    raw_text: str
    posted_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    client_handle: Optional[str] = None
    budget_hint: Optional[str] = None
    lang: Optional[str] = None
    category: Optional[Category] = None
    score: Optional[int] = None
    score_reason: Optional[str] = None
    channel_action: Optional[ChannelAction] = None
    draft: Optional[str] = None
    opening: Optional[str] = None
    status: Status = "new"
    owner: str = "default"      # v2 team-routing placeholder
    tenant: str = "self"        # v2 multi-tenant placeholder
