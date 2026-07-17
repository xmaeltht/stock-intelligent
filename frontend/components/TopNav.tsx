"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/auth";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/discover", label: "Discover" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/compare", label: "Compare" },
];

// Secondary discovery surfaces live under the Discover tab, so keep it lit there.
const DISCOVER_ROUTES = ["/discover", "/stocks", "/radar", "/ideas", "/market", "/backtest"];

export default function TopNav({ online }: { online?: boolean }) {
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();
  const [unread, setUnread] = useState(0);

  // Poll unread alerts while signed in; evaluation happens server-side.
  useEffect(() => {
    if (!user) {
      setUnread(0);
      return;
    }
    let alive = true;
    const check = () =>
      fetch("/api/research/alerts/unread-count", { cache: "no-store" })
        .then((response) => (response.ok ? response.json() : { count: 0 }))
        .then((data) => {
          if (alive) setUnread(Number(data?.count) || 0);
        })
        .catch(() => {});
    check();
    const timer = setInterval(check, 30000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [user, pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    if (href === "/discover") return DISCOVER_ROUTES.some((route) => pathname.startsWith(route));
    return pathname.startsWith(href);
  };
  const initial = (user?.display_name || user?.email || "?").charAt(0).toUpperCase();
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
              {link.href === "/alerts" && unread > 0 && (
                <span className="navBadge">{unread > 9 ? "9+" : unread}</span>
              )}
            </Link>
          ))}
        </div>
        <span className="navMeta">
          <i className={online ? "statusDot statusDot--healthy" : "statusDot"} />
          {online === undefined ? "Connecting" : online ? "Online" : "Offline"}
        </span>
        {!loading &&
          (user ? (
            <span className="navAuth">
              <span className="navAvatar" title={user.email}>{initial}</span>
              <button className="navSignOut" onClick={() => logout()} title="Sign out">
                Sign out
              </button>
            </span>
          ) : (
            <Link href="/login" className="navSignIn">Sign in</Link>
          ))}
      </div>
    </nav>
  );
}
