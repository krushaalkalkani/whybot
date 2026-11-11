import Link from "next/link";
import { site } from "../lib/content";
import { NavLinks } from "./NavLinks";

const repoUrl = (process.env.NEXT_PUBLIC_REPO_URL ?? "").trim() || null;

export function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span
            aria-hidden="true"
            className="grid h-6 w-6 place-items-center rounded-md bg-accent font-mono text-sm font-bold text-bg"
          >
            ?
          </span>
          {site.name}
        </Link>
        <nav aria-label="Main" className="flex items-center gap-0.5 text-sm">
          <NavLinks items={site.nav} />
          {repoUrl ? (
            <a
              href={repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md px-2.5 py-1.5 text-muted hover:text-ink"
            >
              GitHub
            </a>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
