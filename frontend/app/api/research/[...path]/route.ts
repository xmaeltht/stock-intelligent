import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const upstream = new URL(`${backendUrl}/api/v1/${path.join("/")}`);
  upstream.search = request.nextUrl.search;
  try {
    const cookie = request.headers.get("cookie");
    const response = await fetch(upstream, {
      method: request.method,
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
      headers: {
        "content-type": "application/json",
        // Forward the session cookie so authenticated calls reach the backend.
        ...(cookie ? { cookie } : {}),
      },
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    });
    const body = await response.text();
    const headers = new Headers({
      "content-type": response.headers.get("content-type") ?? "application/json",
    });
    // Relay any Set-Cookie (login / logout) back to the browser.
    const setCookies =
      typeof response.headers.getSetCookie === "function"
        ? response.headers.getSetCookie()
        : response.headers.get("set-cookie")
          ? [response.headers.get("set-cookie") as string]
          : [];
    for (const value of setCookies) headers.append("set-cookie", value);
    return new NextResponse(body, { status: response.status, headers });
  } catch {
    return NextResponse.json({ detail: "Research API could not be reached" }, { status: 503 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE, proxy as PUT };
