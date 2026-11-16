"use client";

import { useEffect, useState } from "react";
import { api, CampaignRef, HistoryItem, OfferRef, Stream } from "@/lib/api";
import { useEditor } from "@/store/editor";
import OfferSearch from "./OfferSearch";

export default function Editor() {
  const { campaign, campaignId, loading, error, open, close, reload, history, clearError } = useEditor();

  return (
    <div>
      <section className="card">
        <div className="row">
          <h2 style={{ margin: 0 }}>Редактор кампании</h2>
          {campaignId && (
            <div className="row gap">
              <button onClick={reload} disabled={loading}>{loading ? "Загрузка…" : "Обновить"}</button>
              <button onClick={close}>Другая кампания</button>
            </div>
          )}
        </div>
        {!campaignId && <CampaignPicker onPick={open} />}
        {error && (
          <p className="error">
            {error} <button className="link" onClick={clearError}>×</button>
          </p>
        )}
      </section>

      {campaign && (
        <>
          <section className="card">
            <h3>
              #{campaign.id} {campaign.name} <span className="muted small">/{campaign.alias}</span>
              {campaign.state !== "active" && <span className="tag">{campaign.state}</span>}
            </h3>
            {campaign.streams.length === 0 && <p className="muted">В кампании нет потоков</p>}
            <div className="streams">
              {campaign.streams.map((s) => (
                <StreamCard key={s.id} stream={s} />
              ))}
            </div>
          </section>
          {history.length > 0 && <History items={history} streams={campaign.streams} />}
        </>
      )}
    </div>
  );
}

function CampaignPicker({ onPick }: { onPick: (id: number) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<CampaignRef[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        setItems(await api.campaigns(q));
        setErr(null);
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="picker">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Поиск кампании по имени, ID или alias" autoFocus />
      {err && <p className="error">{err}</p>}
      <ul className="list">
        {loading && items.length === 0 && <li className="muted">Загрузка…</li>}
        {items.map((c) => (
          <li key={c.id} onClick={() => onPick(c.id)}>
            <span className="id">#{c.id}</span> {c.name} <span className="muted small">/{c.alias}</span>
            {c.state !== "active" && <span className="tag">{c.state}</span>}
          </li>
        ))}
        {!loading && items.length === 0 && !err && <li className="muted">Кампаний не найдено</li>}
      </ul>
    </div>
  );
}

const FILTER_NAMES: Record<string, string> = { country: "Страна" };

function StreamCard({ stream }: { stream: Stream }) {
  const { busyStream, drafts, addOffer, removeOffer, setDraft, resetDraft, saveShares } = useEditor();
  const [adding, setAdding] = useState(false);
  const [pick, setPick] = useState<OfferRef | null>(null);
  const busy = busyStream === stream.id;
  const draft = drafts[stream.id];
  const isOffers = stream.schema === "landings";
  const shareOf = (oid: number, base: number) => (draft ? draft[oid] ?? base : base);
  const total = stream.offers.reduce((sum, o) => sum + shareOf(o.offer_id, o.share), 0);

  return (
    <div className={`stream ${busy ? "busy" : ""}`}>
      <div className="stream-head">
        <span className={`dot ${stream.state === "active" ? "on" : ""}`} />
        <b>{stream.name || `Поток #${stream.id}`}</b>
        <span className="muted small">
          #{stream.id} · {stream.type} · позиция {stream.position}
        </span>
      </div>

      {stream.filters.length > 0 && (
        <div className="small">
          Фильтры:{" "}
          {stream.filters.map((f, i) => (
            <span key={i} className="pill">
              {FILTER_NAMES[f.name] ?? f.name} {f.mode === "reject" ? "≠" : "="}{" "}
              {Array.isArray(f.payload) ? f.payload.join(", ") : String(f.payload ?? "")}
            </span>
          ))}
        </div>
      )}
      {stream.action_payload && <div className="small">Редирект → <a href={stream.action_payload} target="_blank" rel="noreferrer">{stream.action_payload}</a></div>}

      {isOffers && (
        <>
          <table className="table offers">
            <thead>
              <tr><th>Оффер</th><th style={{ width: 110 }}>Доля, %</th><th style={{ width: 40 }} /></tr>
            </thead>
            <tbody>
              {stream.offers.map((o) => (
                <tr key={o.offer_id}>
                  <td>
                    <span className="id">[{o.offer_id}]</span> {o.name}
                    {o.state !== "active" && <span className="tag">{o.state}</span>}
                    <div className="bar"><div style={{ width: `${shareOf(o.offer_id, o.share)}%` }} /></div>
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={shareOf(o.offer_id, o.share)}
                      disabled={busy}
                      onChange={(e) => setDraft(stream.id, o.offer_id, Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                    />
                  </td>
                  <td>
                    <button
                      className="danger icon"
                      title="Удалить оффер"
                      disabled={busy}
                      onClick={() => {
                        if (confirm(`Удалить оффер [${o.offer_id}] ${o.name} из потока?`)) removeOffer(stream.id, o.offer_id);
                      }}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
              {stream.offers.length === 0 && (
                <tr><td colSpan={3} className="muted">Офферов нет</td></tr>
              )}
            </tbody>
            <tfoot>
              <tr>
                <td>Итого</td>
                <td className={total === 100 || stream.offers.length === 0 ? "ok" : "bad"}>{total}%</td>
                <td />
              </tr>
            </tfoot>
          </table>

          {draft && (
            <div className="row gap">
              <button className="primary" disabled={busy || total !== 100} onClick={() => saveShares(stream.id)}>
                Сохранить доли
              </button>
              <button onClick={() => resetDraft(stream.id)} disabled={busy}>Отмена</button>
              {total !== 100 && <span className="error small">Сумма должна быть 100%</span>}
            </div>
          )}

          {adding ? (
            <div className="row gap add">
              <div style={{ flex: 1 }}>
                <OfferSearch value={pick} onChange={setPick} exclude={stream.offers.map((o) => o.offer_id)} autoFocus />
              </div>
              <button
                className="primary"
                disabled={!pick || busy}
                onClick={async () => {
                  if (!pick) return;
                  await addOffer(stream.id, pick.id);
                  setPick(null);
                  setAdding(false);
                }}
              >
                Добавить
              </button>
              <button onClick={() => (setAdding(false), setPick(null))}>Отмена</button>
            </div>
          ) : (
            <button className="link" onClick={() => setAdding(true)} disabled={busy}>+ Добавить оффер</button>
          )}
        </>
      )}
    </div>
  );
}

const ACTIONS = { add: "Добавлен", remove: "Удалён", set_shares: "Доли изменены" };

function History({ items, streams }: { items: HistoryItem[]; streams: Stream[] }) {
  const names = Object.fromEntries(streams.flatMap((s) => s.offers.map((o) => [o.offer_id, o.name])));
  const fmt = (l: { offer_id: number; share: number }[]) => l.map((o) => `${o.offer_id}:${o.share}%`).join(", ") || "—";
  return (
    <section className="card">
      <h3>История изменений</h3>
      <table className="table small">
        <thead><tr><th>Когда</th><th>Поток</th><th>Действие</th><th>Было</th><th>Стало</th></tr></thead>
        <tbody>
          {items.map((h) => (
            <tr key={h.id}>
              <td>{h.created_at ? new Date(h.created_at).toLocaleString() : ""}</td>
              <td>#{h.stream_id}</td>
              <td>
                {ACTIONS[h.action]}
                {h.offer_id && ` [${h.offer_id}]${names[h.offer_id] ? " " + names[h.offer_id] : ""}`}
              </td>
              <td>{fmt(h.before)}</td>
              <td>{fmt(h.after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
