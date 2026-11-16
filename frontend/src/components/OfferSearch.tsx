"use client";

import { useEffect, useRef, useState } from "react";
import { api, OfferRef } from "@/lib/api";

type Props = {
  value: OfferRef | null;
  onChange: (o: OfferRef | null) => void;
  exclude?: number[];
  placeholder?: string;
  autoFocus?: boolean;
};

/** Поиск офферов Keitaro с автокомплитом (по имени или ID). */
export default function OfferSearch({ value, onChange, exclude = [], placeholder, autoFocus }: Props) {
  const [text, setText] = useState(value ? label(value) : "");
  const [items, setItems] = useState<OfferRef[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => setText(value ? label(value) : ""), [value]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const query = value && text === label(value) ? "" : text;
        const res = await api.offers(query);
        setItems(res.filter((o) => !exclude.includes(o.id)));
        setActive(0);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, open, exclude.join(",")]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const pick = (o: OfferRef) => {
    onChange(o);
    setText(label(o));
    setOpen(false);
  };

  return (
    <div className="ac" ref={box}>
      <input
        value={text}
        autoFocus={autoFocus}
        placeholder={placeholder ?? "Поиск по офферам…"}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          if (value) onChange(null);
        }}
        onKeyDown={(e) => {
          if (!open) return;
          if (e.key === "ArrowDown") (e.preventDefault(), setActive((a) => Math.min(a + 1, items.length - 1)));
          if (e.key === "ArrowUp") (e.preventDefault(), setActive((a) => Math.max(a - 1, 0)));
          if (e.key === "Enter" && items[active]) (e.preventDefault(), pick(items[active]));
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && (
        <ul className="ac-list">
          {loading && items.length === 0 && <li className="muted">Загрузка…</li>}
          {!loading && items.length === 0 && <li className="muted">Ничего не найдено</li>}
          {items.map((o, i) => (
            <li
              key={o.id}
              className={i === active ? "active" : ""}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => (e.preventDefault(), pick(o))}
            >
              <span className="id">#{o.id}</span> {o.name}
              {o.state && o.state !== "active" && <span className="tag">{o.state}</span>}
            </li>
          ))}
          {loading && items.length > 0 && <li className="muted small">Поиск…</li>}
        </ul>
      )}
    </div>
  );
}

const label = (o: OfferRef) => `[${o.id}] ${o.name}`;
