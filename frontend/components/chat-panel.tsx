"use client";

import { useRef, useEffect, useState, useCallback, KeyboardEvent } from "react";
import { Send, Square, UploadCloud } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ChatMessage } from "@/components/chat-message";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;

interface ChatPanelProps {
  messages: ChatMessageType[];
  isStreaming: boolean;
  onSendMessage: (content: string) => void;
  onImageClick?: (imageId: string) => void;
  uploadedFileId?: string;
  onUpload?: (file: File) => void;
}

export function ChatPanel({
  messages,
  isStreaming,
  onSendMessage,
  onImageClick,
  onUpload,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    onSendMessage(trimmed);
  }, [input, isStreaming, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleFile = useCallback(
    (file: File) => {
      if (!onUpload) return;
      if (file.size > MAX_FILE_SIZE_BYTES) return;
      onUpload(file);
    },
    [onUpload],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback(() => setIsDragging(false), []);

  const isEmpty = messages.length === 0;

  return (
    <div
      className={cn(
        "flex h-full flex-col",
        isDragging && "ring-2 ring-primary ring-inset",
      )}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
    >
      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-4">
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center">
            <UploadCloud className="size-12 text-muted-foreground/40" />
            <div>
              <p className="font-medium text-sm text-muted-foreground">
                No messages yet
              </p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                Upload an image and start asking questions
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((msg, i) => (
              <ChatMessage key={i} message={msg} onImageClick={onImageClick} />
            ))}
            {isStreaming && (
              <div className="flex justify-start">
                <div className="rounded-xl border bg-muted/40 px-4 py-2.5">
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="size-1.5 animate-pulse rounded-full bg-current" />
                    <span className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:150ms]" />
                    <span className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:300ms]" />
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </ScrollArea>

      {/* Input */}
      <div className="border-t bg-background px-4 py-3">
        <div className="flex items-end gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the image… (Enter to send, Shift+Enter for newline)"
            className="min-h-[2.5rem] max-h-40 resize-none"
            rows={1}
            disabled={isStreaming}
          />
          <Button
            size="icon"
            variant={isStreaming ? "destructive" : "default"}
            onClick={handleSend}
            disabled={!isStreaming && !input.trim()}
            title={isStreaming ? "Stop" : "Send"}
          >
            {isStreaming ? <Square /> : <Send />}
          </Button>
        </div>
      </div>
    </div>
  );
}
