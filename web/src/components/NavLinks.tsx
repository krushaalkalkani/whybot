"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLinks({ items }: { items: { href: string; label: string }[] }) {
  const pathname = usePathname();
  return (
    <>
      {items.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-2.5 py-1.5 ${
              active ? "bg-sunken font-medium text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
