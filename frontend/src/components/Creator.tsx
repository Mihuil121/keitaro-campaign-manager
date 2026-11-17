"use client";

import { useEffect } from "react";
import { Ref } from "@/lib/api";
import { useCreator } from "@/store/creator";
import { useEditor } from "@/store/editor";
import { useMeta } from "@/store/meta";
import OfferSearch from "./OfferSearch";

export default function Creator({ onOpenEditor }: { onOpenEditor: () => void }) {
  const { meta, load, loading: metaLoading, error: metaError } = useMeta();
  const { form, setField, applyDefaults, submit, submitting, error, last, created, loadCreated } = useCreator();
  const openCampaign = useEditor((s) => s.open);

  useEffect(() => {
    load();
    loadCreated();
  }, [load, loadCreated]);
  useEffect(() => {
    if (meta) applyDefaults(meta);
  }, [meta, applyDefaults]);

  const prefix = meta?.campaign_prefix ?? "";

  const edit = (id: number) => {
    openCampaign(id);
    onOpenEditor();
  };

  return (
    <div className="grid2">
      <section className="card">
        <h2>Новая кампания</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label>
            <span>Название</span>
            <div className={prefix ? "prefixed" : ""}>
              {prefix && <span className="prefix">{prefix}</span>}
              <input
                value={form.name}
                onChange={(e) => setField("name", stripPrefix(e.target.value, prefix))}
                placeholder={prefix ? "campaign1" : "имя кампании"}
              />
            </div>
            {prefix && <small>Префикс добавляется автоматически (CAMPAIGN_PREFIX в .env)</small>}
          </label>
          <label>
            <span>Гео</span>
            <input
              value={form.geo}
              onChange={(e) => setField("geo", e.target.value.toUpperCase())}
              placeholder="MX, AU, RO…"
            />
            <small>ISO-код страны, можно несколько через запятую</small>
          </label>
          <label>
            <span>Оффер</span>
            <OfferSearch value={form.offer} onChange={(o) => setField("offer", o)} placeholder="поиск по офферам" />
          </label>

          <details className="advanced" open={!meta?.defaults.domain_id || !meta?.defaults.group_id || !meta?.defaults.traffic_source_id}>
            <summary>Домен, группа, источник</summary>
            {metaError && <p className="error">Справочники не загрузились: {metaError}</p>}
            <RefSelect label="Домен" items={meta?.domains} value={form.domain_id} onChange={(v) => setField("domain_id", v)} />
            <RefSelect label="Группа" items={meta?.groups} value={form.group_id} onChange={(v) => setField("group_id", v)} />
            <RefSelect
              label="Источник"
              items={meta?.sources}
              value={form.traffic_source_id}
              onChange={(v) => setField("traffic_source_id", v)}
            />
            <button type="button" className="link" onClick={() => load(true)} disabled={metaLoading}>
              {metaLoading ? "Обновляю…" : "Обновить справочники"}
            </button>
          </details>

          {error && <p className="error">{error}</p>}
          <button className="primary" type="submit" disabled={submitting}>
            {submitting ? "Создаю…" : "Create"}
          </button>
        </form>

        {last && (
          <div className="success">
            <b>Кампания #{last.id} создана.</b>
            {last.url && (
              <div>
                Ссылка: <a href={last.url} target="_blank" rel="noreferrer">{last.url}</a>{" "}
                <button className="link" onClick={() => navigator.clipboard.writeText(last.url!)}>копировать</button>
              </div>
            )}
            <div>
              Поток 1: {last.geo.join(", ")} → Google · Поток 2: оффер #{last.offer_id}
            </div>
            <button className="link" onClick={() => edit(last.id)}>Открыть в редакторе →</button>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Созданные здесь</h2>
        {created.length === 0 ? (
          <p className="muted">Пока пусто</p>
        ) : (
          <table className="table">
            <thead>
              <tr><th>ID</th><th>Название</th><th>Гео</th><th>Оффер</th><th /></tr>
            </thead>
            <tbody>
              {created.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>
                    {c.name}
                    {c.url && <div className="muted small">{c.url}</div>}
                  </td>
                  <td>{c.geo.join(", ")}</td>
                  <td>#{c.offer_id}</td>
                  <td><button className="link" onClick={() => edit(c.id)}>Редактировать</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

/** Если префикс вставили вместе с именем — не дублируем его в поле. */
function stripPrefix(v: string, prefix: string) {
  return prefix && v.toLowerCase().startsWith(prefix.toLowerCase()) ? v.slice(prefix.length) : v;
}

function RefSelect({
  label,
  items,
  value,
  onChange,
}: {
  label: string;
  items?: Ref[];
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">— выбрать —</option>
        {items?.map((i) => (
          <option key={i.id} value={i.id}>
            {i.name} (#{i.id})
          </option>
        ))}
      </select>
    </label>
  );
}
