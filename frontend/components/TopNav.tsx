"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Screener" },
  { href: "/ideas", label: "Ideas" },
  { href: "/market", label: "Market" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/compare", label: "Compare" },
];

export default function TopNav({ online }: { online?: boolean }) {
  const pathname = usePathname();
  return (
    <nav className="topnav">
      <div className="shell">
        <Link className="brand" href="/">
          <span className="brandMark">SI</span>
          <span>Stock Intelligence</span>
        </Link>
        <div className="navLinks">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                link.href === "/"
                  ? pathname === "/" || pathname.startsWith("/stocks") ? "active" : ""
                  : pathname.startsWith(link.href) ? "active" : ""
              }
            >
              {link.label}
            </Link>
          ))}
        </div>
        <span className="navMeta">
          <i className={online ? "statusDot statusDot--healthy" : "statusDot"} />
          {online === undefined ? "Connecting" : online ? "Research API online" : "API offline"}
        </span>
      </div>
    </nav>
  );
}
