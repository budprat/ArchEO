"use client";

import { useReducer, useRef, useCallback } from "react";
import type {
  AppState,
  AppAction,
  ChatMessage,
  UploadedFile,
  ResultImage,
  HistoryEntry,
} from "./types";
import { uploadFile as apiUploadFile, streamChat } from "./api";

const initialState: AppState = {
  messages: [],
  isStreaming: false,
  uploadedFile: null,
  resultImages: [],
  activeImageLayer: "original",
};

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "ADD_MESSAGE":
      return { ...state, messages: [...state.messages, action.message] };

    case "UPDATE_LAST_THINKING": {
      const messages = [...state.messages];
      const lastIdx = messages.length - 1;
      if (lastIdx >= 0 && messages[lastIdx].type === "thinking") {
        messages[lastIdx] = {
          type: "thinking",
          content: messages[lastIdx].content + action.content,
        };
      } else {
        messages.push({ type: "thinking", content: action.content });
      }
      return { ...state, messages };
    }

    case "UPDATE_LAST_AGENT": {
      const messages = [...state.messages];
      const lastIdx = messages.length - 1;
      if (lastIdx >= 0 && messages[lastIdx].type === "agent") {
        messages[lastIdx] = {
          type: "agent",
          content: messages[lastIdx].content + action.content,
        };
      } else {
        messages.push({ type: "agent", content: action.content });
      }
      return { ...state, messages };
    }

    case "SET_STREAMING":
      return { ...state, isStreaming: action.isStreaming };

    case "SET_UPLOADED_FILE":
      return {
        ...state,
        uploadedFile: action.file,
        resultImages: [],
        activeImageLayer: "original",
        messages: [],
      };

    case "ADD_RESULT_IMAGE": {
      // Deduplicate by id — prevent infinite re-render from duplicate images
      const exists = state.resultImages.some((r) => r.id === action.image.id);
      if (exists) return state;
      return { ...state, resultImages: [...state.resultImages, action.image] };
    }

    case "SET_ACTIVE_LAYER":
      return { ...state, activeImageLayer: action.layer };

    case "CLEAR_MESSAGES":
      return { ...state, messages: [] };

    default:
      return state;
  }
}

export function useChat(apiKey?: string) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortControllerRef = useRef<AbortController | null>(null);
  const historyRef = useRef<HistoryEntry[]>([]);
  const lastThinkingRef = useRef<string>("");

  const sendMessage = useCallback(
    (content: string) => {
      const userMessage: ChatMessage = {
        type: "user",
        content,
        fileId: state.uploadedFile?.id,
      };
      dispatch({ type: "ADD_MESSAGE", message: userMessage });
      dispatch({ type: "SET_STREAMING", isStreaming: true });
      lastThinkingRef.current = "";

      historyRef.current = [
        ...historyRef.current,
        { role: "user", content, fileId: state.uploadedFile?.id },
      ];

      const controller = streamChat(
        content,
        state.uploadedFile?.id,
        historyRef.current,
        (event) => {
          const { type, data } = event;

          switch (type) {
            case "thinking": {
              const chunk =
                (data.text as string) ?? (data.content as string) ?? "";
              lastThinkingRef.current += chunk;
              dispatch({
                type: "UPDATE_LAST_THINKING",
                content: chunk,
              });
              break;
            }

            case "tool_call":
              dispatch({
                type: "ADD_MESSAGE",
                message: {
                  type: "tool_call",
                  tool: (data.tool as string) ?? "",
                  params:
                    (data.input as Record<string, unknown>) ??
                    (data.params as Record<string, unknown>) ??
                    {},
                },
              });
              break;

            case "tool_result": {
              const toolName = (data.tool as string) ?? "";
              const toolOutput =
                (data.output as string) ?? (data.result as string) ?? "";
              const resultImages = (data.result_images as string[]) ?? [];
              const imageId =
                resultImages.length > 0
                  ? resultImages[0]
                  : (data.image_id as string | undefined);

              const toolResultMsg: ChatMessage = {
                type: "tool_result",
                tool: toolName,
                result: toolOutput,
                imageId: imageId,
                imageIds: resultImages.length > 0 ? resultImages : undefined,
              };
              dispatch({ type: "ADD_MESSAGE", message: toolResultMsg });

              // Register result images for the image viewer
              // Use result_images from backend, or extract filenames from output text
              let imagesToRegister = resultImages;
              if (imagesToRegister.length === 0 && toolOutput) {
                // Extract .tif/.png filenames from output text (with or without path prefix)
                const matches = toolOutput.match(
                  /([a-zA-Z0-9_-]+)\.(tif|tiff|png|jpg|jpeg)/gi,
                );
                if (matches) {
                  imagesToRegister = [
                    ...new Set(
                      matches.map((m: string) => {
                        const name = m.split("/").pop() ?? m;
                        // Convert .tif to .png (backend converts TIF→PNG)
                        return name.replace(/\.(tif|tiff)$/i, ".png");
                      }),
                    ),
                  ];
                }
              }
              if (imagesToRegister.length > 0 && state.uploadedFile) {
                for (const imgName of imagesToRegister) {
                  const resultImage: ResultImage = {
                    id: imgName,
                    tool: toolName,
                    url: `/api/results/${state.uploadedFile.id}/${imgName}`,
                    label: `${toolName}: ${imgName}`,
                  };
                  dispatch({ type: "ADD_RESULT_IMAGE", image: resultImage });
                }
              }
              break;
            }

            case "agent": {
              // Final answer streamed as chunks — accumulate into agent message
              const agentChunk =
                (data.text as string) ?? (data.content as string) ?? "";
              if (agentChunk) {
                lastThinkingRef.current += agentChunk;
                dispatch({ type: "UPDATE_LAST_AGENT", content: agentChunk });
              }
              break;
            }

            case "message": {
              const msgContent =
                (data.text as string) ?? (data.content as string) ?? "";
              if (msgContent) {
                dispatch({
                  type: "ADD_MESSAGE",
                  message: {
                    type: "agent",
                    content: msgContent,
                    images: data.images as string[] | undefined,
                  },
                });
                historyRef.current = [
                  ...historyRef.current,
                  { role: "assistant", content: msgContent },
                ];
              }
              break;
            }

            case "error":
              dispatch({
                type: "ADD_MESSAGE",
                message: {
                  type: "error",
                  message: (data.message as string) ?? "Unknown error",
                },
              });
              break;

            default:
              break;
          }
        },
        (error) => {
          dispatch({
            type: "ADD_MESSAGE",
            message: { type: "error", message: error.message },
          });
          dispatch({ type: "SET_STREAMING", isStreaming: false });
        },
        () => {
          // Promote accumulated thinking text to an agent message for history
          if (lastThinkingRef.current) {
            historyRef.current = [
              ...historyRef.current,
              { role: "assistant", content: lastThinkingRef.current },
            ];
          }
          lastThinkingRef.current = "";
          dispatch({ type: "SET_STREAMING", isStreaming: false });
        },
        apiKey,
      );

      abortControllerRef.current = controller;
    },
    [state.uploadedFile, apiKey],
  );

  const uploadFile = useCallback(async (file: File) => {
    try {
      const result = await apiUploadFile(file);
      const uploadedFile: UploadedFile = {
        id: result.file_id,
        name: file.name,
        format:
          (result.metadata?.format as string) ??
          file.name.split(".").pop() ??
          "unknown",
        dimensions: (result.metadata?.dimensions as [number, number]) ?? [0, 0],
        bands: (result.metadata?.bands as number) ?? 0,
        crs: (result.metadata?.crs as string | null) ?? null,
        thumbnailUrl: result.thumbnail_url,
      };
      dispatch({ type: "SET_UPLOADED_FILE", file: uploadedFile });
    } catch (error) {
      dispatch({
        type: "ADD_MESSAGE",
        message: {
          type: "error",
          message: error instanceof Error ? error.message : "Upload failed",
        },
      });
    }
  }, []);

  const setFileFromDownload = useCallback(
    (
      fileId: string,
      metadata: Record<string, unknown>,
      thumbnailUrl: string,
    ) => {
      const uploadedFile: UploadedFile = {
        id: fileId,
        name: (metadata?.original_name as string) ?? `sentinel2_${fileId}.tif`,
        format: (metadata?.format as string) ?? "GTiff",
        dimensions: (metadata?.dimensions as [number, number]) ?? [0, 0],
        bands: (metadata?.bands as number) ?? 0,
        crs: (metadata?.crs as string | null) ?? null,
        thumbnailUrl,
      };
      dispatch({ type: "SET_UPLOADED_FILE", file: uploadedFile });
    },
    [],
  );

  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    dispatch({ type: "SET_STREAMING", isStreaming: false });
  }, []);

  const setActiveLayer = useCallback((layer: string) => {
    dispatch({ type: "SET_ACTIVE_LAYER", layer });
  }, []);

  return {
    messages: state.messages,
    isStreaming: state.isStreaming,
    uploadedFile: state.uploadedFile,
    resultImages: state.resultImages,
    activeImageLayer: state.activeImageLayer,
    sendMessage,
    uploadFile,
    setFileFromDownload,
    stopStreaming,
    setActiveLayer,
  };
}
