"use client";

import ReactMarkdown from "react-markdown";
import { ToolCallCard } from "@/components/tool-call-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

function formatToolResult(raw: string): string {
  if (!raw) return "";

  // Try JSON parse first, then Python dict (single quotes → double quotes)
  let parsed: Record<string, unknown> | null = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    try {
      // Python str(dict) uses single quotes — convert to JSON
      const fixed = raw
        .replace(/'/g, '"')
        .replace(/True/g, "true")
        .replace(/False/g, "false")
        .replace(/None/g, "null");
      parsed = JSON.parse(fixed);
    } catch {
      // Not parseable
    }
  }

  if (parsed && typeof parsed === "object") {
    return Object.entries(parsed)
      .map(([k, v]) => {
        if (Array.isArray(v)) {
          if (v.length <= 3)
            return `${k}: ${v.map((x) => (typeof x === "number" ? Number(x).toFixed(2) : x)).join(", ")}`;
          return `${k}: ${v.length} items`;
        }
        if (typeof v === "number") return `${k}: ${Number(v).toFixed(4)}`;
        if (typeof v === "string" && v.includes("/")) {
          return `${k}: ${v.split("/").pop()}`;
        }
        return `${k}: ${v}`;
      })
      .join("\n");
  }

  // Fallback: clean file paths and Python repr artifacts
  return raw
    .replace(/\/[^\s'",\]]*\/([^\s'",\]]+)/g, "$1")
    .replace(/^\{|\}$/g, "")
    .replace(/'/g, "");
}

interface ChatMessageProps {
  message: ChatMessageType;
  onImageClick?: (imageId: string) => void;
}

export function ChatMessage({ message, onImageClick }: ChatMessageProps) {
  switch (message.type) {
    case "user":
      return (
        <div className="flex justify-end">
          <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
            {message.content}
          </div>
        </div>
      );

    case "thinking":
      return (
        <div className="flex justify-start">
          <div className="max-w-[90%] rounded-xl border bg-card px-4 py-3">
            <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </div>
        </div>
      );

    case "tool_call":
      return (
        <div className="flex justify-start">
          <div className="w-full max-w-[90%]">
            <ToolCallCard tool={message.tool} params={message.params} />
          </div>
        </div>
      );

    case "tool_result": {
      // Collect all viewable images from imageId (first) + imageIds (all)
      const allImageIds: string[] = [];
      if (message.imageIds && message.imageIds.length > 0) {
        allImageIds.push(...message.imageIds);
      } else if (message.imageId) {
        allImageIds.push(message.imageId);
      }

      // Also extract image filenames from result text as fallback
      if (allImageIds.length === 0 && message.result) {
        const matches = message.result.match(
          /([a-zA-Z0-9_-]+)\.(tif|tiff|png|jpg|jpeg)/gi,
        );
        if (matches) {
          for (const m of matches) {
            const pngName = m.replace(/\.(tif|tiff)$/i, ".png");
            if (!allImageIds.includes(pngName)) allImageIds.push(pngName);
          }
        }
      }

      return (
        <div className="flex justify-start">
          <div className="max-w-[90%] rounded-xl border border-green-200 bg-green-50 px-4 py-2.5 dark:border-green-900 dark:bg-green-950/30">
            <div className="mb-1 flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">
                {message.tool}
              </Badge>
              <span className="text-xs text-muted-foreground">Result</span>
            </div>
            <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-4">
              {formatToolResult(message.result)}
            </p>
            {allImageIds.length > 0 && onImageClick && (
              <div className="mt-2 flex flex-wrap gap-2">
                {allImageIds.map((imgId) => (
                  <button
                    key={imgId}
                    className="text-xs text-primary underline-offset-2 hover:underline"
                    onClick={() => onImageClick(imgId)}
                    type="button"
                  >
                    View {imgId}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    case "agent":
      return (
        <div className="flex justify-start">
          <div className="max-w-[90%] rounded-xl border bg-card px-4 py-3">
            <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
            {message.images && message.images.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {message.images.map((url, i) => (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    key={i}
                    src={url}
                    alt={`Result ${i + 1}`}
                    className="h-24 w-auto rounded border object-cover"
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      );

    case "error":
      return (
        <div className="flex justify-start">
          <div className="max-w-[90%] rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-2.5">
            <p className="text-xs font-medium text-destructive">Error</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {message.message}
            </p>
          </div>
        </div>
      );

    default:
      return null;
  }
}
