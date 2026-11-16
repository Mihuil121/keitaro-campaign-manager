"""Локальная заглушка Keitaro Admin API — чтобы погонять UI без реального трекера.

    uvicorn tests.mock_server:app --port 9000
    # в .env: KEITARO_URL=http://localhost:9000  KEITARO_API_KEY=test
"""

import httpx
from fastapi import FastAPI, Request, Response

from tests.fake_keitaro import FakeKeitaro

fake = FakeKeitaro()
fake.offers = [
    {"id": 3716, "name": "Mailflow [BEAUTY-RO-BE_0008] prize ro", "state": "active"},
    {"id": 3717, "name": "Mailflow [BEAUTY-RO-BE_0009] spin ro", "state": "active"},
    {"id": 3749, "name": "Mailflow [BEAUTY-MX-BE_0001] prize mx", "state": "active"},
    {"id": 3801, "name": "Dating AU smartlink", "state": "active"},
    {"id": 3802, "name": "Crypto AU lander v2", "state": "active"},
    {"id": 3803, "name": "Sweeps MX iPhone", "state": "disabled"},
]
app = FastAPI()


@app.api_route("/admin_api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    req = httpx.Request(request.method, str(request.url), headers=request.headers.raw, content=await request.body())
    r = fake.handle(req)
    return Response(r.content, status_code=r.status_code, media_type="application/json")
