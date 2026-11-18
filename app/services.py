import asyncio
import logging
import re
import secrets
import string
import time

from sqlalchemy.orm import Session

from app import shares as sh
from app.config import settings
from app.keitaro import KeitaroClient, KeitaroError
from app.models import CreatedCampaign, OfferChange

log = logging.getLogger(__name__)

GEO_RE = re.compile(r"^[A-Z]{2}$")


def parse_geo(raw: str | list[str]) -> list[str]:
    items = raw if isinstance(raw, list) else re.split(r"[\s,;]+", raw)
    codes = [c.strip().upper() for c in items if c and c.strip()]
    bad = [c for c in codes if not GEO_RE.match(c)]
    if not codes or bad:
        raise ValueError(f"Неверный гео-код: {', '.join(bad) or 'пусто'} (нужен ISO-код из 2 букв, напр. AU)")
    return list(dict.fromkeys(codes))


def with_prefix(name: str, prefix: str | None = None) -> str:
    """Добавляет префикс (test_фамилия_), если его ещё нет."""
    prefix = settings.campaign_prefix if prefix is None else prefix
    name = name.strip()
    if prefix and not name.lower().startswith(prefix.lower()):
        name = prefix + name
    return name


def random_alias(n: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def resolve(items: list[dict], ref: str | int | None, label: str) -> int | None:
    """Находит объект по ID или имени (без учёта регистра)."""
    if ref in (None, ""):
        return None
    ref_s = str(ref).strip()
    for it in items:
        if str(it.get("id")) == ref_s:
            return int(it["id"])
    for it in items:
        if str(it.get("name", "")).strip().lower() == ref_s.lower():
            return int(it["id"])
    raise ValueError(f"{label} «{ref_s}» не найден в Keitaro")


def campaign_url(domain: dict | None, alias: str) -> str | None:
    if not domain:
        return None
    name = str(domain.get("name", "")).strip().rstrip("/")
    if not name:
        return None
    if not name.startswith("http"):
        name = ("https://" if domain.get("is_ssl", True) else "http://") + name
    return f"{name}/{alias}"


# ---------------- кэш справочников ----------------

# Keitaro отдаёт полный список офферов медленно (на боевом трекере ~15–20 с),
# поэтому: прогрев при старте, stale-while-revalidate и один запрос на ключ.
_cache: dict[str, tuple[float, list]] = {}
_locks: dict[str, asyncio.Lock] = {}
_refreshing: set[str] = set()
_bg_tasks: set[asyncio.Task] = set()
CACHE_TTL = 300  # после этого отдаём старые данные и обновляем их в фоне


async def _refresh(key: str, fetch) -> None:
    try:
        _cache[key] = (time.monotonic(), await fetch())
    except Exception:
        log.warning("Не удалось обновить кэш %s", key, exc_info=True)
    finally:
        _refreshing.discard(key)


async def cached(key: str, fetch) -> list:
    hit = _cache.get(key)
    if hit:
        if time.monotonic() - hit[0] >= CACHE_TTL and key not in _refreshing:
            _refreshing.add(key)
            task = asyncio.create_task(_refresh(key, fetch))
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)
        return hit[1]
    # холодный кэш: параллельные запросы ждут один и тот же fetch
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if key in _cache:
            return _cache[key][1]
        data = await fetch()
        _cache[key] = (time.monotonic(), data)
        return data


def clear_cache() -> None:
    _cache.clear()


async def warm(k: KeitaroClient) -> None:
    """Прогрев справочников при старте, чтобы первый поиск офферов не ждал Keitaro."""
    results = await asyncio.gather(
        cached("domains", k.domains),
        cached("groups", lambda: k.groups("campaigns")),
        cached("sources", k.traffic_sources),
        cached("offers", k.offers),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            log.warning("Прогрев кэша: %s", r)


async def meta(k: KeitaroClient) -> dict:
    domains = await cached("domains", k.domains)
    groups = await cached("groups", lambda: k.groups("campaigns"))
    sources = await cached("sources", k.traffic_sources)

    def safe(items, ref, label):
        try:
            return resolve(items, ref, label)
        except ValueError:
            return None

    return {
        "domains": [{"id": d["id"], "name": d.get("name")} for d in domains],
        "groups": [{"id": g["id"], "name": g.get("name")} for g in groups],
        "sources": [{"id": s["id"], "name": s.get("name")} for s in sources],
        "campaign_prefix": settings.campaign_prefix,
        "defaults": {
            "domain_id": safe(domains, settings.default_domain, "Домен"),
            "group_id": safe(groups, settings.default_group, "Группа"),
            "traffic_source_id": safe(sources, settings.default_source, "Источник"),
        },
    }


async def search_offers(k: KeitaroClient, q: str = "", limit: int = 20) -> list[dict]:
    offers = await cached("offers", k.offers)
    q = q.strip().lower()
    res = []
    for o in offers:
        if o.get("state") == "deleted":
            continue
        if not q or q in str(o.get("name", "")).lower() or q == str(o.get("id")):
            res.append({"id": o["id"], "name": o.get("name"), "state": o.get("state")})
    return res[:limit]


async def offer_names(k: KeitaroClient) -> dict[int, str]:
    offers = await cached("offers", k.offers)
    return {int(o["id"]): o.get("name", "") for o in offers}


# ---------------- 1. Создаватор ----------------


async def create_campaign(
    k: KeitaroClient,
    db: Session,
    *,
    name: str,
    geo: str | list[str],
    offer_id: int,
    domain_id: int | None = None,
    group_id: int | None = None,
    traffic_source_id: int | None = None,
) -> CreatedCampaign:
    if not name.strip():
        raise ValueError("Название кампании пустое")
    name = with_prefix(name)
    geo_codes = parse_geo(geo)

    m = await meta(k)
    domain_id = domain_id or m["defaults"]["domain_id"]
    group_id = group_id or m["defaults"]["group_id"]
    traffic_source_id = traffic_source_id or m["defaults"]["traffic_source_id"]
    missing = [
        lbl
        for lbl, v in (("домен", domain_id), ("группа", group_id), ("источник", traffic_source_id))
        if not v
    ]
    if missing:
        raise ValueError("Не выбраны: " + ", ".join(missing))

    offers = await cached("offers", k.offers)
    if not any(int(o["id"]) == int(offer_id) for o in offers):
        clear_cache()
        offers = await cached("offers", k.offers)
        if not any(int(o["id"]) == int(offer_id) for o in offers):
            raise ValueError(f"Оффер #{offer_id} не найден в Keitaro")

    alias = random_alias()
    campaign = await k.create_campaign(
        {
            "name": name,
            "alias": alias,
            "type": "position",
            "state": "active",
            "cost_type": "CPC",
            "domain_id": domain_id,
            "group_id": group_id,
            "traffic_source_id": traffic_source_id,
        }
    )
    cid = int(campaign["id"])
    alias = campaign.get("alias") or alias

    try:
        geo_stream = await k.create_stream(
            {
                "campaign_id": cid,
                "type": "regular",
                "name": f"Geo {','.join(geo_codes)} → Google",
                "position": 1,
                "state": "active",
                "schema": "redirect",
                "action_type": "http",
                "action_payload": settings.safe_redirect_url,
                "filters": [{"name": "country", "mode": "accept", "payload": geo_codes}],
            }
        )
        offer_stream = await k.create_stream(
            {
                "campaign_id": cid,
                "type": "regular",
                "name": "Offers",
                "position": 2,
                "state": "active",
                "schema": "landings",
                "action_type": "http",
                "offers": [{"offer_id": int(offer_id), "share": 100, "state": "active"}],
            }
        )
    except KeitaroError:
        # не оставляем в трекере полусобранную кампанию
        try:
            await k.delete_campaign(cid)
        except KeitaroError:
            log.exception("Не удалось откатить кампанию %s", cid)
        raise

    domain = next((d for d in await cached("domains", k.domains) if int(d["id"]) == int(domain_id)), None)
    row = CreatedCampaign(
        keitaro_id=cid,
        name=name,
        alias=alias,
        geo=geo_codes,
        offer_id=int(offer_id),
        domain_id=domain_id,
        group_id=group_id,
        traffic_source_id=traffic_source_id,
        geo_stream_id=int(geo_stream["id"]),
        offer_stream_id=int(offer_stream["id"]),
        url=campaign_url(domain, alias),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------- 2. Редактор ----------------


def active_offers(stream: dict) -> list[dict]:
    return [o for o in stream.get("offers") or [] if o.get("state", "active") != "deleted"]


def offers_payload(items: list[dict]) -> list[dict]:
    return [
        {"offer_id": int(o["offer_id"]), "share": int(o["share"]), "state": o.get("state") or "active"}
        for o in items
    ]


async def stream_view(k: KeitaroClient, stream: dict) -> dict:
    names = await offer_names(k)
    offers = active_offers(stream)
    return {
        "id": stream["id"],
        "name": stream.get("name"),
        "type": stream.get("type"),
        "schema": stream.get("schema"),
        "position": stream.get("position"),
        "state": stream.get("state"),
        "action_payload": stream.get("action_payload") if stream.get("schema") == "redirect" else None,
        "filters": [
            {"name": f.get("name"), "mode": f.get("mode"), "payload": f.get("payload")}
            for f in stream.get("filters") or []
        ],
        "offers": [
            {
                "offer_id": int(o["offer_id"]),
                "name": names.get(int(o["offer_id"]), f"#{o['offer_id']}"),
                "share": int(o.get("share") or 0),
                "state": o.get("state", "active"),
            }
            for o in offers
        ],
        "shares_total": sum(int(o.get("share") or 0) for o in offers),
    }


async def campaign_view(k: KeitaroClient, campaign_id: int) -> dict:
    c = await k.campaign(campaign_id)
    streams = sorted(await k.streams(campaign_id), key=lambda s: s.get("position") or 0)
    return {
        "id": c["id"],
        "name": c.get("name"),
        "alias": c.get("alias"),
        "state": c.get("state"),
        "streams": [await stream_view(k, s) for s in streams if s.get("state") != "deleted"],
    }


async def _save(k, db, campaign_id, stream, action, offer_id, before, after_items) -> dict:
    updated = await k.update_stream(int(stream["id"]), {"offers": offers_payload(after_items)})
    db.add(
        OfferChange(
            campaign_id=campaign_id,
            stream_id=int(stream["id"]),
            action=action,
            offer_id=offer_id,
            before=offers_payload(before),
            after=offers_payload(after_items),
        )
    )
    db.commit()
    # PUT может вернуть поток без offers — тогда перечитываем
    if not isinstance(updated, dict) or "offers" not in updated:
        updated = await k.stream(int(stream["id"]))
    return await stream_view(k, updated)


async def _load_stream(k: KeitaroClient, campaign_id: int, stream_id: int) -> dict:
    stream = await k.stream(stream_id)
    if int(stream.get("campaign_id", campaign_id)) != int(campaign_id):
        raise ValueError("Поток не принадлежит кампании")
    if stream.get("schema") != "landings":
        raise ValueError("В этом потоке нет офферов (схема не «Лендинги и офферы»)")
    return stream


async def add_offer(k, db, campaign_id: int, stream_id: int, offer_id: int) -> dict:
    stream = await _load_stream(k, campaign_id, stream_id)
    before = active_offers(stream)
    if any(int(o["offer_id"]) == int(offer_id) for o in before):
        raise ValueError(f"Оффер #{offer_id} уже есть в потоке")
    if int(offer_id) not in await offer_names(k):
        clear_cache()
        if int(offer_id) not in await offer_names(k):
            raise ValueError(f"Оффер #{offer_id} не найден в Keitaro")
    new_shares = sh.after_add([int(o.get("share") or 0) for o in before])
    after = [dict(o, share=s) for o, s in zip(before, new_shares)]
    after.append({"offer_id": int(offer_id), "share": new_shares[-1], "state": "active"})
    return await _save(k, db, campaign_id, stream, "add", int(offer_id), before, after)


async def remove_offer(k, db, campaign_id: int, stream_id: int, offer_id: int) -> dict:
    stream = await _load_stream(k, campaign_id, stream_id)
    before = active_offers(stream)
    idx = next((i for i, o in enumerate(before) if int(o["offer_id"]) == int(offer_id)), None)
    if idx is None:
        raise ValueError(f"Оффера #{offer_id} нет в потоке")
    new_shares = sh.after_remove([int(o.get("share") or 0) for o in before], idx)
    rest = before[:idx] + before[idx + 1 :]
    after = [dict(o, share=s) for o, s in zip(rest, new_shares)]
    return await _save(k, db, campaign_id, stream, "remove", int(offer_id), before, after)


async def set_shares(k, db, campaign_id: int, stream_id: int, shares: dict[int, int]) -> dict:
    stream = await _load_stream(k, campaign_id, stream_id)
    before = active_offers(stream)
    ids = {int(o["offer_id"]) for o in before}
    if set(shares) != ids:
        raise ValueError("Нужно указать доли для всех офферов потока")
    if any(v < 0 for v in shares.values()):
        raise ValueError("Доля не может быть отрицательной")
    if sum(shares.values()) != 100:
        raise ValueError(f"Сумма долей должна быть 100%, сейчас {sum(shares.values())}%")
    after = [dict(o, share=shares[int(o["offer_id"])]) for o in before]
    return await _save(k, db, campaign_id, stream, "set_shares", None, before, after)
