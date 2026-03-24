"use client";

import ReactMarkdown from "react-markdown";
import { ToolCallCard } from "@/components/tool-call-card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

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

    case "tool_result":
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
              {message.result}
            </p>
            {message.imageId && onImageClick && (
              <button
                className="mt-2 text-xs text-primary underline-offset-2 hover:underline"
                onClick={() => onImageClick(message.imageId!)}
                type="button"
              >
                View result image
              </button>
            )}
          </div>
        </div>
      );

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
