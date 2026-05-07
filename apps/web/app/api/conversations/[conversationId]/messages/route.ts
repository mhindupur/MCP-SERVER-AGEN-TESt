import { NextRequest } from "next/server";

const BACKEND_BASE =
  process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8002";

export const runtime = "nodejs";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  const { conversationId } = await params;

  const upstream = await fetch(`${BACKEND_BASE}/conversations/${conversationId}/messages`, {
    headers: { Cookie: req.headers.get("cookie") || "" }
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" }
  });
}

