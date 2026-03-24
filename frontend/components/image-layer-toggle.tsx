"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ResultImage } from "@/lib/types";

interface ImageLayerToggleProps {
  activeLayer: string;
  resultImages: ResultImage[];
  onLayerChange: (layer: string) => void;
}

export function ImageLayerToggle({
  activeLayer,
  resultImages,
  onLayerChange,
}: ImageLayerToggleProps) {
  if (resultImages.length === 0) return null;

  return (
    <Tabs value={activeLayer} onValueChange={onLayerChange}>
      <TabsList>
        <TabsTrigger value="original">Original</TabsTrigger>
        {resultImages.map((img) => (
          <TabsTrigger key={img.id} value={img.id}>
            {img.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
