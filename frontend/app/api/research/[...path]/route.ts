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
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Research API could not be reached" }, { status: 503 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE, proxy as PUT };
