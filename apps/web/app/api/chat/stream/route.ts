import { NextRequest } from "next/server";

const BACKEND_BASE =
  process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8002";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.text();

  const upstream = await fetch(`${BACKEND_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": req.headers.get("content-type") || "application/json",
      Accept: "text/event-stream",
      Cookie: req.headers.get("cookie") || ""
    },
    body
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "text/event-stream",
      "cache-control": "no-cache",
      connection: "keep-alive"
    }
  });
}

