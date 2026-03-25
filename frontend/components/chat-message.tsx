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
          <div className="max-w-[90%] rounded-xl border bg-muted/40 px-4 py-2.5">
            <span className="mb-1 block text-xs font-medium text-amber-600 dark:text-amber-400">
              Thinking...
            </span>
            <p className="text-xs text-muted-foreground whitespace-pre-wrap">
              {message.content}
            </p>
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
      // Extract image filename from result text (paths like /.../_mcp_temp/file.tif or /.../_mcp_temp/file.png)
      const imgMatch =
        message.result?.match(/\/([^/]+)\.(tif|tiff|png|jpg|jpeg)\s*$/i) ||
        message.result?.match(/\/([^/]+)\.(tif|tiff|png|jpg|jpeg)/i);
      const resultImgName = imgMatch ? `${imgMatch[1]}.png` : message.imageId;

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
            {resultImgName && onImageClick && (
              <button
                className="mt-2 text-xs text-primary underline-offset-2 hover:underline"
                onClick={() => onImageClick(resultImgName)}
                type="button"
              >
                View result image
              </button>
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
