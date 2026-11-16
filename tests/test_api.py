def create(client, **kw):
    body = {"name": "Test camp", "geo": "au", "offer_id": 2, **kw}
    return client.post("/api/campaigns", json=body)


def test_meta_resolves_defaults(client):
    m = client.get("/api/meta").json()
    assert m["defaults"] == {"domain_id": 1, "group_id": 7, "traffic_source_id": 3}


def test_offers_search(client):
    r = client.get("/api/offers", params={"q": "offer 3"}).json()
    assert [o["id"] for o in r] == [3]


def test_create_campaign(client, fake):
    r = create(client)
    assert r.status_code == 201, r.text
    data = r.json()
    c = fake.campaigns[data["id"]]
    assert c["domain_id"] == 1 and c["group_id"] == 7 and c["traffic_source_id"] == 3
    assert c["type"] == "position" and c["name"] == "Test camp"
    assert data["url"] == f"https://in.posdk.xyz/{c['alias']}"

    geo, offer = sorted(
        (s for s in fake.streams.values() if s["campaign_id"] == data["id"]), key=lambda s: s["position"]
    )
    assert geo["schema"] == "redirect" and geo["action_type"] == "http"
    assert geo["action_payload"] == "https://google.com"
    assert geo["filters"] == [{"name": "country", "mode": "accept", "payload": ["AU"]}]
    assert offer["schema"] == "landings"
    assert [(o["offer_id"], o["share"]) for o in offer["offers"]] == [(2, 100)]

    assert client.get("/api/campaigns/created").json()[0]["id"] == data["id"]


def test_create_validation(client):
    assert create(client, geo="AUS").status_code == 400
    assert create(client, offer_id=999).status_code == 400
    assert create(client, name=" ").status_code == 400


def test_create_rolls_back_on_stream_error(client, fake):
    fake.fail_stream_create = True
    r = create(client)
    assert r.status_code in (400, 422, 502)
    assert all(c["state"] == "deleted" for c in fake.campaigns.values())
    assert client.get("/api/campaigns/created").json() == []


def offers_of(view):
    return [(o["offer_id"], o["share"]) for o in view["offers"]]


def test_editor_add_remove(client, fake):
    data = create(client).json()
    cid, sid = data["id"], data["offer_stream_id"]

    v = client.post(f"/api/campaigns/{cid}/streams/{sid}/offers", json={"offer_id": 3}).json()
    assert offers_of(v) == [(2, 50), (3, 50)] and v["shares_total"] == 100

    v = client.post(f"/api/campaigns/{cid}/streams/{sid}/offers", json={"offer_id": 4}).json()
    assert offers_of(v) == [(2, 34), (3, 33), (4, 33)]

    # дубль
    assert client.post(f"/api/campaigns/{cid}/streams/{sid}/offers", json={"offer_id": 4}).status_code == 400

    v = client.delete(f"/api/campaigns/{cid}/streams/{sid}/offers/2").json()
    assert offers_of(v) == [(3, 50), (4, 50)]
    # изменения реально ушли в Keitaro
    assert [(o["offer_id"], o["share"]) for o in fake.streams[sid]["offers"]] == [(3, 50), (4, 50)]

    v = client.put(f"/api/campaigns/{cid}/streams/{sid}/shares", json={"shares": {"3": 70, "4": 30}}).json()
    assert offers_of(v) == [(3, 70), (4, 30)]
    bad = client.put(f"/api/campaigns/{cid}/streams/{sid}/shares", json={"shares": {"3": 70, "4": 20}})
    assert bad.status_code == 400

    hist = client.get(f"/api/campaigns/{cid}/history").json()
    assert [h["action"] for h in hist] == ["set_shares", "remove", "add", "add"]

    view = client.get(f"/api/campaigns/{cid}").json()
    assert len(view["streams"]) == 2 and view["streams"][0]["filters"][0]["payload"] == ["AU"]


def test_editor_rejects_redirect_stream(client):
    data = create(client).json()
    r = client.post(f"/api/campaigns/{data['id']}/streams/{data['geo_stream_id']}/offers", json={"offer_id": 3})
    assert r.status_code == 400


def test_campaign_list(client):
    create(client, name="Alpha")
    create(client, name="Beta")
    assert [c["name"] for c in client.get("/api/campaigns", params={"q": "alp"}).json()] == ["Alpha"]
