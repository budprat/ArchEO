"use client";

import { useRef, useState, useCallback } from "react";
import { UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

interface UploadZoneProps {
  onUpload: (file: File) => void;
  hasFile: boolean;
}

export function UploadZone({ onUpload, hasFile }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setError(
          `File too large. Maximum size is 50 MB (got ${(file.size / 1024 / 1024).toFixed(1)} MB).`,
        );
        return;
      }
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

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  if (hasFile) return null;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-6">
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex w-full min-h-[300px] cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-16 text-center transition-colors",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/50",
        )}
      >
        <UploadCloud className="size-14 text-muted-foreground" />
        <div>
          <p className="font-medium text-base">
            Drop a satellite / aerial image here
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            GeoTIFF, PNG, JPEG — max 50 MB
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".tif,.tiff,.png,.jpg,.jpeg,.geotiff"
          className="hidden"
          onChange={onInputChange}
        />
      </div>
      {error && <p className="text-xs text-destructive text-center">{error}</p>}
    </div>
  );
}
