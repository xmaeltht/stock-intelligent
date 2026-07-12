import { NextResponse } from "next/server";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET() {
  try {
    const response = await fetch(`${backendUrl}/api/v1/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });

    if (!response.ok) {
      return NextResponse.json(
        { status: "unavailable", detail: `Backend returned ${response.status}` },
        { status: 503 },
      );
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json(
      { status: "unavailable", detail: "Backend could not be reached" },
      { status: 503 },
    );
  }
}

