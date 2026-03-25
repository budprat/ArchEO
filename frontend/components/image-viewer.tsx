"use client";

import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ImageViewerProps {
  src: string;
  alt: string;
}

export function ImageViewer({ src, alt }: ImageViewerProps) {
  return (
    <div className="relative overflow-hidden rounded-xl border bg-muted h-full min-h-[400px]">
      <TransformWrapper
        initialScale={1}
        minScale={0.5}
        maxScale={8}
        centerOnInit
      >
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="absolute top-2 right-2 z-10 flex gap-1">
              <Button
                size="icon-sm"
                variant="secondary"
                onClick={() => zoomIn()}
                title="Zoom in"
              >
                <ZoomIn />
              </Button>
              <Button
                size="icon-sm"
                variant="secondary"
                onClick={() => zoomOut()}
                title="Zoom out"
              >
                <ZoomOut />
              </Button>
              <Button
                size="icon-sm"
                variant="secondary"
                onClick={() => resetTransform()}
                title="Reset zoom"
              >
                <Maximize2 />
              </Button>
            </div>
            <TransformComponent
              wrapperStyle={{ width: "100%", height: "100%" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt={alt}
                className="max-w-full max-h-[60vh] object-contain"
              />
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  );
}
