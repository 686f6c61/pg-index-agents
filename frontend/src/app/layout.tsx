/**
 * PG Index Agents - Layout principal
 * https://github.com/686f6c61/pg-index-agents
 *
 * Layout raiz de la aplicacion Next.js. Define la estructura HTML base,
 * las fuentes tipograficas (Geist Sans y Mono), y el contenedor principal
 * con el header de navegacion.
 *
 * Este archivo se renderiza en el servidor y envuelve todas las paginas
 * de la aplicacion.
 *
 * @author 686f6c61
 * @license MIT
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Header } from "@/components/layout/Header";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PG Index Agents - PostgreSQL Database Intelligence",
  description: "Intelligent agents for PostgreSQL index analysis and maintenance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen`}
      >
        <Header />
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
