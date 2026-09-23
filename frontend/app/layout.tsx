import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Электрокомплект — ИИ-консультант",
  description: "ИИ-ассистент для чата на сайте ekt.kz",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">{children}</body>
    </html>
  );
}
