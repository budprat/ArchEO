"use client";
import { useState, useEffect } from "react";

interface MapSelectorProps {
  onDownloadComplete: (
    fileId: string,
    metadata: Record<string, unknown>,
    thumbnailUrl: string,
  ) => void;
}

const PRESETS = [
  { name: "Caral", lat: -10.8933, lon: -77.5203 },
  { name: "Nazca Lines", lat: -14.735, lon: -75.13 },
  { name: "Machu Picchu", lat: -13.1631, lon: -72.545 },
  { name: "Chan Chan", lat: -8.106, lon: -79.0745 },
  { name: "Cusco", lat: -13.532, lon: -71.9675 },
  { name: "Huaca del Sol", lat: -8.1325, lon: -79.0015 },
  { name: "Pachacamac", lat: -12.2275, lon: -76.8985 },
  { name: "Sacsayhuaman", lat: -13.5094, lon: -71.9821 },
  { name: "Ollantaytambo", lat: -13.2588, lon: -72.2636 },
  { name: "Choquequirao", lat: -13.3921, lon: -72.8607 },
  { name: "Sechin", lat: -9.4669, lon: -78.2753 },
  { name: "Sipan", lat: -6.8044, lon: -79.5969 },
  { name: "Kuelap", lat: -6.4167, lon: -77.9214 },
  { name: "Chavin de Huantar", lat: -9.5947, lon: -77.1769 },
  { name: "Tiwanaku", lat: -16.5544, lon: -68.6733 },
];

export function MapSelector({ onDownloadComplete }: MapSelectorProps) {
  const [mounted, setMounted] = useState(false);
  const [mapKey, setMapKey] = useState(0);
  const [lat, setLat] = useState(-10.8933);
  useEffect(() => setMounted(true), []);
  const [lon, setLon] = useState(-77.5203);
  const [status, setStatus] = useState<
    "idle" | "downloading" | "processing" | "done" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  const handlePreset = (preset: (typeof PRESETS)[0]) => {
    setLat(preset.lat);
    setLon(preset.lon);
    setMapKey(Date.now());
  };

  const handleDownload = async () => {
    setStatus("downloading");
    setMessage("Searching for best Sentinel-2 scene...");

    try {
      const res = await fetch("/api/download-sentinel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lon, size: 100 }),
      });
      const { job_id } = await res.json();

      // Poll for completion
      const poll = setInterval(async () => {
        const statusRes = await fetch(`/api/download-status/${job_id}`);
        const data = await statusRes.json();

        if (data.status === "done") {
          clearInterval(poll);
          if (data.file_id) {
            setStatus("done");
            setMessage(
              `Downloaded! Date: ${data.date?.split("T")[0] || "?"}, Cloud: ${data.cloud_cover?.toFixed(1) || "?"}%`,
            );
            onDownloadComplete(data.file_id, data.metadata, data.thumbnail_url);
          } else if (data.upload_error) {
            setStatus("error");
            setMessage(`Upload failed: ${data.upload_error}`);
          } else {
            setStatus("processing");
            setMessage("Processing upload...");
          }
        } else if (data.status === "error") {
          clearInterval(poll);
          setStatus("error");
          setMessage(data.error || "Download failed");
        }
      }, 2000);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Download failed");
    }
  };

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <h3 className="text-sm font-medium">Download Sentinel-2 Data</h3>

      {/* Preset locations */}
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.name}
            onClick={() => handlePreset(p)}
            className="rounded-md border px-2 py-0.5 text-xs hover:bg-muted transition-colors"
          >
            {p.name}
          </button>
        ))}
      </div>

      {/* Coordinate inputs + Go button */}
      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <label className="text-xs text-muted-foreground">Latitude</label>
          <input
            type="number"
            step="0.001"
            value={lat}
            onChange={(e) => setLat(parseFloat(e.target.value))}
            className="w-full rounded-md border bg-background px-2 py-1 text-sm"
          />
        </div>
        <div className="flex-1">
          <label className="text-xs text-muted-foreground">Longitude</label>
          <input
            type="number"
            step="0.001"
            value={lon}
            onChange={(e) => setLon(parseFloat(e.target.value))}
            className="w-full rounded-md border bg-background px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={() => setMapKey(Date.now())}
          className="rounded-md border bg-muted px-2.5 py-1 text-sm font-medium hover:bg-muted/80"
          title="Go to coordinates"
        >
          Go
        </button>
      </div>

      {/* Download button */}
      <button
        onClick={handleDownload}
        disabled={status === "downloading" || status === "processing"}
        className="w-full rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {status === "downloading"
          ? "Downloading..."
          : status === "processing"
            ? "Processing..."
            : "Download Sentinel-2 (100x100, 10m)"}
      </button>

      {/* Status message */}
      {message && (
        <p
          className={`text-xs ${
            status === "error"
              ? "text-destructive"
              : status === "done"
                ? "text-green-600"
                : "text-muted-foreground"
          }`}
        >
          {message}
        </p>
      )}

      {/* Mini map preview using OSM embed — client-only to avoid hydration mismatch */}
      {mounted && (
        <div className="rounded-md border overflow-hidden h-36">
          <iframe
            key={`${lat}-${lon}-${mapKey}`}
            src={`https://www.openstreetmap.org/export/embed.html?bbox=${lon - 0.02},${lat - 0.015},${lon + 0.02},${lat + 0.015}&layer=mapnik&marker=${lat},${lon}`}
            className="w-full h-full border-0"
            title="Location preview"
          />
        </div>
      )}
    </div>
  );
}
