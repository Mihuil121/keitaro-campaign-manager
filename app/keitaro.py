"""Тонкий асинхронный клиент Keitaro Admin API v1.

Документация: https://admin-api.docs.keitaro.io
Авторизация — заголовок `Api-Key`.
"""

from typing import Any

import httpx

from app.config import settings


class KeitaroError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Keitaro {status}: {message}")
        self.status = status
        self.message = message


class KeitaroClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.api_base,
            headers={"Api-Key": api_key if api_key is not None else settings.keitaro_api_key},
            timeout=30,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kw) -> Any:
        try:
            r = await self._client.request(method, url, **kw)
        except httpx.HTTPError as e:
            raise KeitaroError(502, f"Keitaro недоступен: {e}") from e
        if r.status_code >= 400:
            try:
                body = r.json()
                msg = body.get("error") or body.get("message") or r.text
            except Exception:
                msg = r.text
            raise KeitaroError(r.status_code, str(msg)[:500])
        if not r.content:
            return None
        return r.json()

    # --- справочники ---
    async def domains(self) -> list[dict]:
        return await self._request("GET", "/domains")

    async def groups(self, type_: str = "campaigns") -> list[dict]:
        return await self._request("GET", "/groups", params={"type": type_})

    async def traffic_sources(self) -> list[dict]:
        return await self._request("GET", "/traffic_sources")

    async def offers(self) -> list[dict]:
        return await self._request("GET", "/offers")

    # --- кампании ---
    async def campaigns(self) -> list[dict]:
        return await self._request("GET", "/campaigns")

    async def campaign(self, campaign_id: int) -> dict:
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def create_campaign(self, payload: dict) -> dict:
        return await self._request("POST", "/campaigns", json=payload)

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._request("DELETE", f"/campaigns/{campaign_id}")

    # --- потоки ---
    async def streams(self, campaign_id: int) -> list[dict]:
        return await self._request("GET", f"/campaigns/{campaign_id}/streams")

    async def stream(self, stream_id: int) -> dict:
        return await self._request("GET", f"/streams/{stream_id}")

    async def create_stream(self, payload: dict) -> dict:
        return await self._request("POST", "/streams", json=payload)

    async def update_stream(self, stream_id: int, payload: dict) -> dict:
        return await self._request("PUT", f"/streams/{stream_id}", json=payload)
