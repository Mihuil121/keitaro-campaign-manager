# Keitaro wrapper

Обёртка над [Keitaro Admin API](https://admin-api.docs.keitaro.io):

1. **Создаватор кампаний** — по названию (к нему автоматически добавляется префикс `test_фамилия_` из `CAMPAIGN_PREFIX`), гео и ID оффера создаёт кампанию с доменом, группой и источником и двумя потоками:
   - поток 1 — фильтр «Страна = гео» → редирект на `https://google.com`;
   - поток 2 — «Лендинги и офферы» → выбранный оффер (100%).
2. **Редактор кампании** — выбор любой кампании трекера, просмотр потоков, добавление и удаление офферов, ручная правка долей.

Стек: **FastAPI + SQLAlchemy 2 + Alembic** (бэкенд), **Next.js 15 + React 19 + Zustand** (фронт).

```
app/            FastAPI: клиент Keitaro, бизнес-логика, модели БД
alembic/        миграции
frontend/       Next.js (App Router) + Zustand
tests/          pytest + in-memory заглушка Keitaro (и mock-сервер для UI)
```

## Быстрый старт

Нужны Python 3.11+ и Node.js 18.18+.

### 1. Бэкенд

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # вписать KEITARO_API_KEY и свою фамилию в CAMPAIGN_PREFIX
alembic upgrade head                 # создаёт таблицы (по умолчанию SQLite ./app.db)
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

**API-ключ**: админка Keitaro → «Обслуживание» → «Пользователи» → ваш пользователь → «API-ключи» → создать.

### 2. Фронт

```bash
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

Next.js проксирует `/api/*` на бэкенд (`API_URL`, по умолчанию `http://localhost:8000`, см. `frontend/.env.example`).
Прод-сборка: `npm run build && npm start`.

## Настройки (`.env`)

| Переменная | Назначение |
|---|---|
| `KEITARO_URL` | адрес трекера, напр. `https://tlgk.host` |
| `KEITARO_API_KEY` | ключ Admin API (заголовок `Api-Key`) |
| `KEITARO_DEFAULT_DOMAIN` / `_GROUP` / `_SOURCE` | значения по умолчанию для создаватора — ID **или** имя (напр. `FORTESTS`). В UI их можно поменять |
| `CAMPAIGN_PREFIX` | префикс имён кампаний по правилам теста: `test_фамилия_`. Добавляется к названию автоматически, если его ещё нет: `campaign1` → `test_ivanov_campaign1` |
| `SAFE_REDIRECT_URL` | куда уводить трафик из гео (по умолчанию `https://google.com`) |
| `DATABASE_URL` | SQLAlchemy URL. SQLite по умолчанию; для Postgres: `postgresql+psycopg://user:pass@host/db` (+ `pip install psycopg[binary]`) |
| `CORS_ORIGINS` | если фронт ходит в API напрямую, а не через прокси Next |

## Миграции

```bash
alembic upgrade head                                   # применить все
alembic downgrade -1                                   # откатить последнюю
alembic revision --autogenerate -m "описание"          # после изменения app/models.py
alembic current / alembic history                      # состояние
```

URL базы берётся из `DATABASE_URL`. Таблицы:

- `created_campaigns` — кампании, созданные через создаватор (ID в Keitaro, alias, гео, оффер, ID потоков, ссылка);
- `offer_changes` — журнал редактора: действие, оффер, доли «было/стало».

## Как считаются доли

Keitaro требует, чтобы доли активных офферов потока были целыми и давали ровно 100%. Логика в `app/shares.py`:

- **добавление** — новый оффер получает `100/n`, остальные уменьшаются пропорционально. Если доли были равными, они остаются равными: 100 → 50/50 → 34/33/33 → 25×4;
- **удаление** — освободившаяся доля делится между оставшимися пропорционально их долям: 60/20/20 без первого → 50/50;
- если доли были равными с точностью до округления (34/33/33), после изменения они снова делятся поровну: 34/33/33 минус любой → 50/50, а не 51/49;
- **ручная правка** — можно задать доли вручную, сохранение доступно только при сумме 100%;
- округление методом наибольшего остатка, поэтому сумма всегда ровно 100.

Каждое действие сразу пишется в Keitaro через `PUT /streams/{id}` (передаётся полный список `offers`) и попадает в журнал.

## API бэкенда

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/api/meta` | домены, группы, источники и значения по умолчанию |
| GET | `/api/offers?q=` | поиск офферов (автокомплит) |
| POST | `/api/campaigns` | создать кампанию `{name, geo, offer_id, domain_id?, group_id?, traffic_source_id?}` |
| GET | `/api/campaigns/created` | созданные через создаватор |
| GET | `/api/campaigns?q=` | кампании трекера |
| GET | `/api/campaigns/{id}` | кампания с потоками и офферами |
| POST | `/api/campaigns/{id}/streams/{sid}/offers` | добавить оффер `{offer_id}` |
| DELETE | `/api/campaigns/{id}/streams/{sid}/offers/{offer_id}` | удалить оффер |
| PUT | `/api/campaigns/{id}/streams/{sid}/shares` | задать доли `{shares: {offer_id: share}}` |
| GET | `/api/campaigns/{id}/history` | журнал изменений |

Если создание потока упало, кампания удаляется в Keitaro, чтобы в трекере не осталась наполовину собранная кампания.

## Тесты и работа без трекера

```bash
pytest -q
```

Тесты используют in-memory заглушку Keitaro (`tests/fake_keitaro.py`) и проверяют payload кампании и потоков, валидацию, откат при ошибке, а также добавление, удаление и правку долей.

Чтобы посмотреть UI без доступа к трекеру:

```bash
uvicorn tests.mock_server:app --port 9000
# в .env: KEITARO_URL=http://localhost:9000, KEITARO_API_KEY=test, KEITARO_DEFAULT_DOMAIN=in.posdk.xyz
```
