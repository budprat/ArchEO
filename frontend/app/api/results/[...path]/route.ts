import { NextRequest } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const joinedPath = path.join("/");
  const res = await fetch(`${API_BASE}/api/results/${joinedPath}`);
  return new Response(res.body, {
    status: res.status,
    headers: {
      "Content-Type":
        res.headers.get("Content-Type") ?? "application/octet-stream",
    },
  });
}
