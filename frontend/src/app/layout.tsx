import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Keitaro wrapper", description: "Создание и редактирование кампаний Keitaro" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
