export type ChatMessage =
  | { type: "user"; content: string; fileId?: string }
  | { type: "thinking"; content: string }
  | { type: "tool_call"; tool: string; params: Record<string, unknown> }
  | {
      type: "tool_result";
      tool: string;
      result: string;
      imageId?: string;
      imageIds?: string[];
    }
  | { type: "agent"; content: string; images?: string[] }
  | { type: "error"; message: string };

export interface UploadedFile {
  id: string;
  name: string;
  format: string;
  dimensions: [number, number];
  bands: number;
  crs: string | null;
  thumbnailUrl: string;
}

export interface ResultImage {
  id: string;
  tool: string;
  url: string;
  label: string;
}

export interface AppState {
  messages: ChatMessage[];
  isStreaming: boolean;
  uploadedFile: UploadedFile | null;
  resultImages: ResultImage[];
  activeImageLayer: string;
}

export interface HistoryEntry {
  role: "user" | "assistant";
  content: string;
  fileId?: string;
}

export type AppAction =
  | { type: "ADD_MESSAGE"; message: ChatMessage }
  | { type: "UPDATE_LAST_THINKING"; content: string }
  | { type: "UPDATE_LAST_AGENT"; content: string }
  | { type: "SET_STREAMING"; isStreaming: boolean }
  | { type: "SET_UPLOADED_FILE"; file: UploadedFile }
  | { type: "ADD_RESULT_IMAGE"; image: ResultImage }
  | { type: "SET_ACTIVE_LAYER"; layer: string }
  | { type: "CLEAR_MESSAGES" };
