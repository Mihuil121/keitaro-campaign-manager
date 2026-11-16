"""In-memory имитация Keitaro Admin API для тестов."""

import json
import re

import httpx


class FakeKeitaro:
    def __init__(self):
        self.domains = [{"id": 1, "name": "in.posdk.xyz", "is_ssl": True}]
        self.groups = [{"id": 7, "name": "FORTESTS", "type": "campaigns"}]
        self.sources = [{"id": 3, "name": "FORTESTS"}]
        self.offers = [{"id": i, "name": f"Offer {i}", "state": "active"} for i in range(1, 8)]
        self.campaigns: dict[int, dict] = {}
        self.streams: dict[int, dict] = {}
        self.requests: list[tuple[str, str, dict | None]] = []
        self.fail_stream_create = False
        self._cid = 100
        self._sid = 500

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, req: httpx.Request) -> httpx.Response:
        if req.headers.get("Api-Key") != "test":
            return httpx.Response(401, json={"error": "Unauthorized"})
        path = req.url.path.removeprefix("/admin_api/v1")
        body = json.loads(req.content) if req.content else None
        self.requests.append((req.method, path, body))
        m, p = req.method, path

        if m == "GET" and p == "/domains":
            return httpx.Response(200, json=self.domains)
        if m == "GET" and p == "/groups":
            return httpx.Response(200, json=self.groups)
        if m == "GET" and p == "/traffic_sources":
            return httpx.Response(200, json=self.sources)
        if m == "GET" and p == "/offers":
            return httpx.Response(200, json=self.offers)
        if m == "GET" and p == "/campaigns":
            return httpx.Response(200, json=list(self.campaigns.values()))
        if m == "POST" and p == "/campaigns":
            self._cid += 1
            c = {"id": self._cid, "state": "active", **body}
            self.campaigns[self._cid] = c
            return httpx.Response(200, json=c)
        if mm := re.fullmatch(r"/campaigns/(\d+)", p):
            cid = int(mm[1])
            if cid not in self.campaigns:
                return httpx.Response(404, json={"error": "Not found"})
            if m == "DELETE":
                self.campaigns[cid]["state"] = "deleted"
                return httpx.Response(204)
            return httpx.Response(200, json=self.campaigns[cid])
        if mm := re.fullmatch(r"/campaigns/(\d+)/streams", p):
            cid = int(mm[1])
            return httpx.Response(200, json=[s for s in self.streams.values() if s["campaign_id"] == cid])
        if m == "POST" and p == "/streams":
            if self.fail_stream_create:
                return httpx.Response(422, json={"error": "bad stream"})
            self._sid += 1
            s = {"id": self._sid, "filters": [], "offers": [], **body}
            s["offers"] = [{"id": i, "stream_id": self._sid, **o} for i, o in enumerate(s["offers"])]
            self.streams[self._sid] = s
            return httpx.Response(200, json=s)
        if mm := re.fullmatch(r"/streams/(\d+)", p):
            sid = int(mm[1])
            if sid not in self.streams:
                return httpx.Response(404, json={"error": "Not found"})
            if m == "PUT":
                s = self.streams[sid]
                s.update(body)
                s["offers"] = [{"id": i, "stream_id": sid, **o} for i, o in enumerate(s.get("offers", []))]
                return httpx.Response(200, json=s)
            return httpx.Response(200, json=self.streams[sid])
        return httpx.Response(404, json={"error": f"no route {m} {p}"})
