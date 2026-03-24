'use client';

import { useReducer, useRef, useCallback } from 'react';
import type {
  AppState,
  AppAction,
  ChatMessage,
  UploadedFile,
  ResultImage,
  HistoryEntry,
} from './types';
import { uploadFile as apiUploadFile, streamChat } from './api';

const initialState: AppState = {
  messages: [],
  isStreaming: false,
  uploadedFile: null,
  resultImages: [],
  activeImageLayer: 'original',
};

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] };

    case 'UPDATE_LAST_THINKING': {
      const messages = [...state.messages];
      const lastIdx = messages.length - 1;
      if (lastIdx >= 0 && messages[lastIdx].type === 'thinking') {
        messages[lastIdx] = {
          type: 'thinking',
          content: messages[lastIdx].content + action.content,
        };
      } else {
        messages.push({ type: 'thinking', content: action.content });
      }
      return { ...state, messages };
    }

    case 'SET_STREAMING':
      return { ...state, isStreaming: action.isStreaming };

    case 'SET_UPLOADED_FILE':
      return { ...state, uploadedFile: action.file };

    case 'ADD_RESULT_IMAGE':
      return { ...state, resultImages: [...state.resultImages, action.image] };

    case 'SET_ACTIVE_LAYER':
      return { ...state, activeImageLayer: action.layer };

    case 'CLEAR_MESSAGES':
      return { ...state, messages: [] };

    default:
      return state;
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortControllerRef = useRef<AbortController | null>(null);
  const historyRef = useRef<HistoryEntry[]>([]);

  const sendMessage = useCallback(
    (content: string) => {
      const userMessage: ChatMessage = {
        type: 'user',
        content,
        fileId: state.uploadedFile?.id,
      };
      dispatch({ type: 'ADD_MESSAGE', message: userMessage });
      dispatch({ type: 'SET_STREAMING', isStreaming: true });

      historyRef.current = [
        ...historyRef.current,
        { role: 'user', content, fileId: state.uploadedFile?.id },
      ];

      const controller = streamChat(
        content,
        state.uploadedFile?.id,
        historyRef.current,
        (event) => {
          const { type, data } = event;

          switch (type) {
            case 'thinking':
              dispatch({
                type: 'UPDATE_LAST_THINKING',
                content: (data.content as string) ?? '',
              });
              break;

            case 'tool_call':
              dispatch({
                type: 'ADD_MESSAGE',
                message: {
                  type: 'tool_call',
                  tool: (data.tool as string) ?? '',
                  params: (data.params as Record<string, unknown>) ?? {},
                },
              });
              break;

            case 'tool_result': {
              const toolResultMsg: ChatMessage = {
                type: 'tool_result',
                tool: (data.tool as string) ?? '',
                result: (data.result as string) ?? '',
                imageId: data.image_id as string | undefined,
              };
              dispatch({ type: 'ADD_MESSAGE', message: toolResultMsg });

              if (data.image_id && data.image_url) {
                const resultImage: ResultImage = {
                  id: data.image_id as string,
                  tool: (data.tool as string) ?? '',
                  url: data.image_url as string,
                  label: (data.label as string) ?? (data.tool as string) ?? 'Result',
                };
                dispatch({ type: 'ADD_RESULT_IMAGE', image: resultImage });
              }
              break;
            }

            case 'agent': {
              const agentContent = (data.content as string) ?? '';
              dispatch({
                type: 'ADD_MESSAGE',
                message: {
                  type: 'agent',
                  content: agentContent,
                  images: data.images as string[] | undefined,
                },
              });
              historyRef.current = [
                ...historyRef.current,
                { role: 'assistant', content: agentContent },
              ];
              break;
            }

            case 'error':
              dispatch({
                type: 'ADD_MESSAGE',
                message: {
                  type: 'error',
                  message: (data.message as string) ?? 'Unknown error',
                },
              });
              break;

            default:
              break;
          }
        },
        (error) => {
          dispatch({
            type: 'ADD_MESSAGE',
            message: { type: 'error', message: error.message },
          });
          dispatch({ type: 'SET_STREAMING', isStreaming: false });
        },
        () => {
          dispatch({ type: 'SET_STREAMING', isStreaming: false });
        }
      );

      abortControllerRef.current = controller;
    },
    [state.uploadedFile]
  );

  const uploadFile = useCallback(async (file: File) => {
    try {
      const result = await apiUploadFile(file);
      const uploadedFile: UploadedFile = {
        id: result.file_id,
        name: file.name,
        format: (result.metadata?.format as string) ?? file.name.split('.').pop() ?? 'unknown',
        dimensions: (result.metadata?.dimensions as [number, number]) ?? [0, 0],
        bands: (result.metadata?.bands as number) ?? 0,
        crs: (result.metadata?.crs as string | null) ?? null,
        thumbnailUrl: result.thumbnail_url,
      };
      dispatch({ type: 'SET_UPLOADED_FILE', file: uploadedFile });
    } catch (error) {
      dispatch({
        type: 'ADD_MESSAGE',
        message: {
          type: 'error',
          message: error instanceof Error ? error.message : 'Upload failed',
        },
      });
    }
  }, []);

  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    dispatch({ type: 'SET_STREAMING', isStreaming: false });
  }, []);

  const setActiveLayer = useCallback((layer: string) => {
    dispatch({ type: 'SET_ACTIVE_LAYER', layer });
  }, []);

  return {
    messages: state.messages,
    isStreaming: state.isStreaming,
    uploadedFile: state.uploadedFile,
    resultImages: state.resultImages,
    activeImageLayer: state.activeImageLayer,
    sendMessage,
    uploadFile,
    stopStreaming,
    setActiveLayer,
  };
}
