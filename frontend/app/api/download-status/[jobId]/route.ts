import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  const res = await fetch(`${API_BASE}/api/download-status/${jobId}`);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
