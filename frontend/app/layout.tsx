import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NovelDownloader Web",
  description: "Convierte novelas archivadas en PDFs elegantes desde el navegador.",
  icons: {
    icon: "/logo.png",
    shortcut: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
