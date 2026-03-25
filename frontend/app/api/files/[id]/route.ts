import { NextRequest } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const type = req.nextUrl.searchParams.get("type") ?? "thumbnail";
  const res = await fetch(`${API_BASE}/api/files/${id}?type=${type}`);
  return new Response(res.body, {
    status: res.status,
    headers: {
      "Content-Type":
        res.headers.get("Content-Type") ?? "application/octet-stream",
    },
  });
}
