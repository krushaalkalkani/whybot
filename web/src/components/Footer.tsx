import { site } from "../lib/content";

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto w-full max-w-6xl px-4 py-5 text-sm text-muted sm:px-6">
        {site.footer}
      </div>
    </footer>
  );
}
