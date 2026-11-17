import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import services
from app.db import Base, get_db, make_engine
from app.keitaro import KeitaroClient
from app.main import app
from tests.fake_keitaro import FakeKeitaro


@pytest.fixture
def fake():
    return FakeKeitaro()


@pytest.fixture
def client(fake, tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    from app import config

    monkeypatch.setattr(
        services,
        "settings",
        config.Settings(
            default_group="FORTESTS", default_source="3", default_domain="in.posdk.xyz", campaign_prefix="test_ivanov_"
        ),
    )
    services.clear_cache()
    app.dependency_overrides[get_db] = _db
    app.state.keitaro = KeitaroClient(base_url="http://k/admin_api/v1", api_key="test", transport=fake.transport())
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    app.state.keitaro = None
