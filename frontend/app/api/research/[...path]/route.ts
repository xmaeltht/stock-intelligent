import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const upstream = new URL(`${backendUrl}/api/v1/${path.join("/")}`);
  upstream.search = request.nextUrl.search;
  try {
    const response = await fetch(upstream, {
      method: request.method,
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
      headers: { "content-type": "application/json" },
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    });
    const body = await response.text();
    const isRead = request.method === "GET" || request.method === "HEAD";
    // Brief browser caching absorbs duplicate navigation/poll requests while
    // keeping quotes fresh. Mutations and health failures are never cached.
    const cacheControl = isRead && response.ok
      ? path.at(-1) === "summary"
        ? "private, max-age=5, stale-while-revalidate=10"
        : "private, max-age=12, stale-while-revalidate=30"
      : "no-store";
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
        "cache-control": cacheControl,
        "x-content-type-options": "nosniff",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Research API could not be reached" }, { status: 503 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE, proxy as PUT };
