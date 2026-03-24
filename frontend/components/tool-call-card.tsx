"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ToolCallCardProps {
  tool: string;
  params: Record<string, unknown>;
}

export function ToolCallCard({ tool, params }: ToolCallCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border bg-muted/30 text-sm">
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        {open ? (
          <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
        )}
        <span className="text-muted-foreground text-xs">Calling tool</span>
        <Badge variant="outline" className="font-mono text-xs">
          {tool}
        </Badge>
      </button>
      {open && (
        <div className="border-t px-3 py-2">
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-muted-foreground">
            {JSON.stringify(params, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
