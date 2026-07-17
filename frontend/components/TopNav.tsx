"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/discover", label: "Discover" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/compare", label: "Compare" },
];

// Secondary discovery surfaces live under the Discover tab, so keep it lit there.
const DISCOVER_ROUTES = ["/discover", "/stocks", "/radar", "/ideas", "/market", "/backtest"];

export default function TopNav({ online }: { online?: boolean }) {
  const pathname = usePathname();
  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    if (href === "/discover") return DISCOVER_ROUTES.some((route) => pathname.startsWith(route));
    return pathname.startsWith(href);
  };
  return (
    <nav className="topnav">
      <div className="shell">
        <Link className="brand" href="/">
          <span className="brandMark">SI</span>
          <span>Stock Intelligence</span>
        </Link>
        <div className="navLinks">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} className={isActive(link.href) ? "active" : ""}>
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
