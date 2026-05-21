import { NextRequest } from "next/server";

const BACKEND_BASE =
  process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8002";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const roleArn = url.searchParams.get("aws_role_arn") || "";
  const region = url.searchParams.get("aws_region") || "ap-south-1";

  const qs = new URLSearchParams({
    aws_role_arn: roleArn,
    aws_region: region
  });

  const upstream = await fetch(`${BACKEND_BASE}/aws/infra/topology?${qs.toString()}`, {
    method: "GET",
    headers: { Cookie: req.headers.get("cookie") || "" }
  });

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") || "application/json" }
  });
}
