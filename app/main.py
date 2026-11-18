import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.config import settings
from app.db import get_db
from app.keitaro import KeitaroClient, KeitaroError
from app.models import CreatedCampaign, OfferChange

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not getattr(app.state, "keitaro", None):
        app.state.keitaro = KeitaroClient()
    warm = asyncio.create_task(services.warm(app.state.keitaro))
    yield
    warm.cancel()
    await app.state.keitaro.close()


app = FastAPI(title="Keitaro wrapper", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def keitaro(request: Request) -> KeitaroClient:
    return request.app.state.keitaro


@app.exception_handler(KeitaroError)
async def keitaro_error(_: Request, e: KeitaroError):
    status = e.status if e.status in (400, 404, 422) else 502
    return JSONResponse({"detail": f"Keitaro: {e.message}"}, status_code=status)


@app.exception_handler(ValueError)
async def value_error(_: Request, e: ValueError):
    return JSONResponse({"detail": str(e)}, status_code=400)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite не хранит tz — значения пишутся в UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ---------- схемы ----------


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo: str | list[str]
    offer_id: int
    domain_id: int | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None


class OfferIn(BaseModel):
    offer_id: int


class SharesIn(BaseModel):
    shares: dict[int, int]


# ---------- справочники ----------


@app.get("/api/meta")
async def get_meta(k: KeitaroClient = Depends(keitaro)):
    return await services.meta(k)


@app.post("/api/cache/clear")
async def clear_cache():
    services.clear_cache()
    return {"ok": True}


@app.get("/api/offers")
async def get_offers(q: str = "", limit: int = 20, k: KeitaroClient = Depends(keitaro)):
    return await services.search_offers(k, q, min(limit, 100))


# ---------- 1. создаватор ----------


@app.post("/api/campaigns", status_code=201)
async def create_campaign(body: CampaignIn, k: KeitaroClient = Depends(keitaro), db: Session = Depends(get_db)):
    row = await services.create_campaign(k, db, **body.model_dump())
    return _created(row)


@app.get("/api/campaigns/created")
def created_campaigns(db: Session = Depends(get_db)):
    rows = db.scalars(select(CreatedCampaign).order_by(CreatedCampaign.id.desc()).limit(50))
    return [_created(r) for r in rows]


def _created(r: CreatedCampaign) -> dict:
    return {
        "id": r.keitaro_id,
        "name": r.name,
        "alias": r.alias,
        "geo": r.geo,
        "offer_id": r.offer_id,
        "url": r.url,
        "geo_stream_id": r.geo_stream_id,
        "offer_stream_id": r.offer_stream_id,
        "created_at": _iso(r.created_at),
    }


# ---------- 2. редактор ----------


@app.get("/api/campaigns")
async def list_campaigns(q: str = "", k: KeitaroClient = Depends(keitaro)):
    items = await k.campaigns()
    q = q.strip().lower()
    res = [
        {"id": c["id"], "name": c.get("name"), "alias": c.get("alias"), "state": c.get("state")}
        for c in items
        if c.get("state") != "deleted"
        and (not q or q in str(c.get("name", "")).lower() or q == str(c["id"]) or q == str(c.get("alias", "")).lower())
    ]
    return sorted(res, key=lambda c: -int(c["id"]))[:100]


@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, k: KeitaroClient = Depends(keitaro)):
    return await services.campaign_view(k, campaign_id)


@app.post("/api/campaigns/{campaign_id}/streams/{stream_id}/offers")
async def add_offer(
    campaign_id: int, stream_id: int, body: OfferIn, k: KeitaroClient = Depends(keitaro), db: Session = Depends(get_db)
):
    return await services.add_offer(k, db, campaign_id, stream_id, body.offer_id)


@app.delete("/api/campaigns/{campaign_id}/streams/{stream_id}/offers/{offer_id}")
async def remove_offer(
    campaign_id: int, stream_id: int, offer_id: int, k: KeitaroClient = Depends(keitaro), db: Session = Depends(get_db)
):
    return await services.remove_offer(k, db, campaign_id, stream_id, offer_id)


@app.put("/api/campaigns/{campaign_id}/streams/{stream_id}/shares")
async def set_shares(
    campaign_id: int, stream_id: int, body: SharesIn, k: KeitaroClient = Depends(keitaro), db: Session = Depends(get_db)
):
    return await services.set_shares(k, db, campaign_id, stream_id, body.shares)


@app.get("/api/campaigns/{campaign_id}/history")
def history(campaign_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(OfferChange).where(OfferChange.campaign_id == campaign_id).order_by(OfferChange.id.desc()).limit(50)
    )
    return [
        {
            "id": r.id,
            "stream_id": r.stream_id,
            "action": r.action,
            "offer_id": r.offer_id,
            "before": r.before,
            "after": r.after,
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


