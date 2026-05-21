import { NextRequest } from "next/server";

const BACKEND_BASE =
  process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8002";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const upstream = await fetch(`${BACKEND_BASE}/actions/run`, {
    method: "POST",
    headers: {
      "Content-Type": req.headers.get("content-type") || "application/json",
      Cookie: req.headers.get("cookie") || ""
    },
    body
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" }
  });
}

