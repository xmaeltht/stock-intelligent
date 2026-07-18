"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import TopNav from "../../components/TopNav";
import { useAuth } from "../../lib/auth";

function LoginContent() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const { login, register } = useAuth();

  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState(params.get("error") === "google" ? "Google sign-in failed. Try again or use email." : "");
  const [busy, setBusy] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    fetch("/api/research/auth/providers")
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data) setGoogleEnabled(Boolean(data.google));
      })
      .catch(() => {});
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, displayName);
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="shell authShell">
      <div className="card authCard">
        <div className="authHead">
          <span className="brandMark">SI</span>
          <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p>
            {mode === "login"
              ? "Sign in to track your watchlist and portfolio."
              : "Free forever — save watchlists and get your holdings scored."}
          </p>
        </div>

        {googleEnabled && (
          <>
            {/* Real navigation (not next/link) so the browser follows the OAuth redirects. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a className="googleBtn" href="/api/research/auth/google/start">
              <span className="googleG">G</span> Continue with Google
            </a>
            <div className="authDivider"><span>or</span></div>
          </>
        )}

        <form className="authForm" onSubmit={submit}>
          {mode === "signup" && (
            <label>
              Name <span className="authOpt">(optional)</span>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Pat"
                autoComplete="name"
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "signup" ? 8 : undefined}
              required
            />
          </label>

          {error && <div className="authError">{error}</div>}

          <button className="authSubmit" type="submit" disabled={busy}>
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="authSwitch">
          {mode === "login" ? (
            <>
              New here?{" "}
              <button type="button" onClick={() => { setMode("signup"); setError(""); }}>
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={() => { setMode("login"); setError(""); }}>
                Sign in
              </button>
            </>
          )}
        </div>

        <p className="authNote">
          Rules-based research — not investment advice. By continuing you agree to use this for
          research only. <Link href="/discover" className="homeLink">Browse without an account →</Link>
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <>
      <TopNav online />
      <Suspense fallback={<main className="shell authShell"><p className="notice">Loading…</p></main>}>
        <LoginContent />
      </Suspense>
    </>
  );
}
