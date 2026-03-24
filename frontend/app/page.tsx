"use client";

import { useChat } from "@/lib/use-chat";
import { Header } from "@/components/header";
import { ChatPanel } from "@/components/chat-panel";
import { ImageViewer } from "@/components/image-viewer";
import { ImageLayerToggle } from "@/components/image-layer-toggle";
import { FileMetadata } from "@/components/file-metadata";
import { UploadZone } from "@/components/upload-zone";

export default function Home() {
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
  } = useChat();

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
      <Header />
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
