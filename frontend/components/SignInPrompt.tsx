"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function SignInPrompt({
  title,
  body,
  icon = "🔒",
}: {
  title: string;
  body: string;
  icon?: string;
}) {
  const pathname = usePathname();
  const next = encodeURIComponent(pathname || "/");
  return (
    <div className="card signInPrompt">
      <div className="signInInner">
        <div className="signInIcon">{icon}</div>
        <h2>{title}</h2>
        <p>{body}</p>
        <div className="signInActions">
          <Link href={`/login?next=${next}`} className="btn">Sign in</Link>
          <Link href={`/login?next=${next}`} className="btn btn--ghost">Create free account</Link>
        </div>
        <p className="signInNote">
          Free forever. <Link href="/discover" className="homeLink">Keep browsing without an account →</Link>
        </p>
      </div>
    </div>
  );
}
