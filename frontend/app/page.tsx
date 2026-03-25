"use client";

import { useState, useEffect } from "react";
import { useChat } from "@/lib/use-chat";
import { Header } from "@/components/header";
import { ChatPanel } from "@/components/chat-panel";
import { ImageViewer } from "@/components/image-viewer";
import { ImageLayerToggle } from "@/components/image-layer-toggle";
import { FileMetadata } from "@/components/file-metadata";
import { UploadZone } from "@/components/upload-zone";

const API_KEY_STORAGE_KEY = "archeo-agent-api-key";

export default function Home() {
  const [apiKey, setApiKey] = useState("");

  // Load API key from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(API_KEY_STORAGE_KEY);
    if (stored) setApiKey(stored);
  }, []);

  const handleApiKeyChange = (key: string) => {
    setApiKey(key);
    if (key) {
      localStorage.setItem(API_KEY_STORAGE_KEY, key);
    } else {
      localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
  };

  const {
    messages,
    isStreaming,
    uploadedFile,
    resultImages,
    activeImageLayer,
    sendMessage,
    uploadFile,
    stopStreaming,
    setActiveLayer,
  } = useChat(apiKey);

  // Determine the active image src
  let activeImageSrc: string | null = null;
  if (uploadedFile) {
    if (activeImageLayer === "original") {
      activeImageSrc = uploadedFile.thumbnailUrl;
    } else {
      const match = resultImages.find((img) => img.id === activeImageLayer);
      activeImageSrc = match?.url ?? uploadedFile.thumbnailUrl;
    }
  }

  const handleImageClick = (imageId: string) => {
    setActiveLayer(imageId);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header apiKey={apiKey} onApiKeyChange={handleApiKeyChange} />
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Chat */}
        <div className="flex w-[55%] flex-col border-r overflow-hidden">
          <ChatPanel
            messages={messages}
            isStreaming={isStreaming}
            onSendMessage={sendMessage}
            onImageClick={handleImageClick}
            uploadedFileId={uploadedFile?.id}
            onUpload={uploadFile}
          />
        </div>

        {/* Right panel: Image + metadata */}
        <div className="flex w-[45%] flex-col gap-4 overflow-y-auto p-4">
          {!uploadedFile ? (
            <UploadZone onUpload={uploadFile} hasFile={false} />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground truncate">
                  {uploadedFile.name}
                </span>
                <label className="cursor-pointer text-xs text-primary hover:underline">
                  Upload New
                  <input
                    type="file"
                    className="hidden"
                    accept=".tif,.tiff,.png,.jpg,.jpeg"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) uploadFile(f);
                    }}
                  />
                </label>
              </div>
              {activeImageSrc && (
                <div className="flex-1 min-h-0">
                  <ImageViewer src={activeImageSrc} alt={uploadedFile.name} />
                </div>
              )}
              <ImageLayerToggle
                activeLayer={activeImageLayer}
                resultImages={resultImages}
                onLayerChange={setActiveLayer}
              />
              <FileMetadata file={uploadedFile} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
