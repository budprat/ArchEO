import type { HistoryEntry } from "./types";

const API_BASE = "";

export async function uploadFile(file: File): Promise<{
  file_id: string;
  metadata: Record<string, unknown>;
  thumbnail_url: string;
}> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Upload failed: ${response.status} ${text}`);
  }

  return response.json();
}

export function streamChat(
  message: string,
  fileId: string | undefined,
  history: HistoryEntry[],
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
  onError: (error: Error) => void,
  onDone: () => void,
  apiKey?: string,
): AbortController {
  const controller = new AbortController();

  const body: Record<string, unknown> = { message, history };
  if (fileId) {
    body.file_id = fileId;
  }
  if (apiKey) {
    body.api_key = apiKey;
  }

  (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Chat request failed: ${response.status} ${text}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEventType = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed === ":") continue;

          if (trimmed.startsWith("event: ")) {
            currentEventType = trimmed.slice(7).trim();
          } else if (trimmed.startsWith("data: ")) {
            const data = trimmed.slice(6);
            if (data === "[DONE]") {
              onDone();
              return;
            }
            if (currentEventType === "done") {
              onDone();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              onEvent({ type: currentEventType || "unknown", data: parsed });
            } catch {
              // non-JSON data line, skip
            }
            currentEventType = "";
          }
        }
      }

      onDone();
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        // Streaming was aborted intentionally
        return;
      }
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  return controller;
}
