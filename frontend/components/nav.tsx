"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Pipeline" },
  { href: "/review", label: "Review" },
  { href: "/architecture", label: "Architecture" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="flex items-center gap-6 border-b border-border bg-surface px-4 py-3 sm:px-6">
      <Link href="/" className="flex items-center gap-2">
        <span
          aria-hidden
          className="inline-block size-3 rounded-sm bg-accent"
        />
        <span className="text-sm font-semibold tracking-tight text-primary">
          Construction Ops
        </span>
      </Link>

      <nav className="flex items-center gap-1">
        {LINKS.map((link) => {
          const active =
            link.href === "/"
              ? pathname === "/"
              : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-surface-active font-medium text-primary"
                  : "text-tertiary hover:text-primary",
              )}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
