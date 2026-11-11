import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { site } from "../lib/content";
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
  title: {
    default: `${site.name} - ${site.tagline}`,
    template: `%s - ${site.name}`,
  },
  description: site.description,
  applicationName: site.name,
  authors: [{ name: "Krushal Kalkani" }],
  openGraph: {
    type: "website",
    siteName: site.name,
    title: `${site.name} - ${site.tagline}`,
    description: site.description,
  },
  twitter: {
    card: "summary",
    title: `${site.name} - ${site.tagline}`,
    description: site.description,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f8f6" },
    { media: "(prefers-color-scheme: dark)", color: "#0e0f0e" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <Header />
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
