import logging
import sqlite3
from pathlib import Path
from gig_radar.models import Lead

log = logging.getLogger("gig_radar")


class LeadStore:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS leads ("
            " id TEXT PRIMARY KEY, status TEXT, data TEXT)"
        )
        self.conn.commit()

    def exists(self, lead_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM leads WHERE id=?", (lead_id,))
        return cur.fetchone() is not None

    def upsert(self, lead: Lead) -> None:
        self.conn.execute(
            "INSERT INTO leads(id,status,data) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data",
            (lead.id, lead.status, lead.model_dump_json()),
        )
        self.conn.commit()

    def get(self, lead_id: str) -> Lead | None:
        row = self.conn.execute("SELECT data FROM leads WHERE id=?", (lead_id,)).fetchone()
        return Lead.model_validate_json(row["data"]) if row else None

    def all(self) -> list[Lead]:
        out = []
        for r in self.conn.execute("SELECT data FROM leads").fetchall():
            try:
                out.append(Lead.model_validate_json(r["data"]))
            except Exception as e:                      # noqa: BLE001 isolate per-row failures
                log.warning("skipping corrupt lead row: %r", e)
        return out

    def filter_unseen(self, leads: list[Lead]) -> list[Lead]:
        seen: set[str] = set()
        out = []
        for l in leads:
            if l.id in seen or self.exists(l.id):
                continue
            seen.add(l.id)
            out.append(l)
        return out

    def mark(self, lead_id: str, status: str) -> None:
        lead = self.get(lead_id)
        if lead is None:
            return
        lead.status = status
        self.upsert(lead)
