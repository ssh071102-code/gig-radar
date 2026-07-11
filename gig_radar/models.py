from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Source = Literal["reddit", "rss", "upwork"]
Category = Literal["ai-integration", "ai-video", "automation", "other"]
ChannelAction = Literal["comment", "email", "dm", "upwork_manual"]
Status = Literal["new", "scored", "unscored", "pushed"]


class RawItem(BaseModel):
    source: Source
    external_id: str            # stable id within the source (post id / guid)
    url: str
    title: str
    raw_text: str
    posted_at: datetime | None = None
    client_handle: str | None = None


class Lead(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str                     # stable hash: source + external_id
    source: Source
    url: str
    title: str
    raw_text: str
    posted_at: datetime | None = None
    fetched_at: datetime | None = None
    client_handle: str | None = None
    budget_hint: str | None = None
    lang: str | None = None
    category: Category | None = None
    score: int | None = None
    score_reason: str | None = None
    channel_action: ChannelAction | None = None
    draft: str | None = None
    opening: str | None = None
    status: Status = "new"
    owner: str = "default"      # v2 team-routing placeholder
