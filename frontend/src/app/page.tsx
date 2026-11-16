"use client";

import { useState } from "react";
import Creator from "@/components/Creator";
import Editor from "@/components/Editor";

type Tab = "create" | "edit";

export default function Home() {
  const [tab, setTab] = useState<Tab>("create");
  return (
    <main className="wrap">
      <header className="top">
        <h1>Keitaro wrapper</h1>
        <nav className="tabs">
          <button className={tab === "create" ? "on" : ""} onClick={() => setTab("create")}>Создаватор</button>
          <button className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Редактор</button>
        </nav>
      </header>
      {tab === "create" ? <Creator onOpenEditor={() => setTab("edit")} /> : <Editor />}
    </main>
  );
}
