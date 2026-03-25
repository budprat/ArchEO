"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface HeaderProps {
  apiKey: string;
  onApiKeyChange: (key: string) => void;
}

export function Header({ apiKey, onApiKeyChange }: HeaderProps) {
  const [open, setOpen] = useState(false);
  const [inputKey, setInputKey] = useState(apiKey);

  const handleSave = () => {
    onApiKeyChange(inputKey.trim());
    setOpen(false);
  };

  const isKeySet = apiKey.length > 0;
  const maskedKey = isKeySet
    ? `${apiKey.slice(0, 10)}...${apiKey.slice(-4)}`
    : "Not set";

  return (
    <header className="flex items-center justify-between border-b bg-background px-6 py-3">
      <div className="flex flex-col">
        <h1 className="text-lg font-semibold leading-tight">ArchEO-Agent</h1>
        <p className="text-xs text-muted-foreground">
          Archaeological Image Analysis
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Badge variant="secondary">Claude Haiku 4.5</Badge>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            className={`inline-flex items-center justify-center rounded-md px-3 py-1.5 text-xs font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
              isKeySet
                ? "border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                : "bg-destructive text-destructive-foreground hover:bg-destructive/90"
            }`}
          >
            {isKeySet ? "API Key Set" : "Set API Key"}
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Anthropic API Key</DialogTitle>
              <DialogDescription>
                Enter your Claude API key. It will be stored in your browser
                only and sent with each request.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-3">
              <input
                type="password"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                placeholder="sk-ant-api03-..."
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              />
              {isKeySet && (
                <p className="text-xs text-muted-foreground">
                  Current: {maskedKey}
                </p>
              )}
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSave}>
                  Save
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </header>
  );
}
