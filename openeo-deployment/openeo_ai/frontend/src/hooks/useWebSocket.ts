import { useCallback, useEffect, useRef, useState } from 'react'
import { Message, Visualization, QualityMetrics, ToolCall, ThinkingStep, ClarificationQuestion } from '@/types'
import { generateId } from '@/lib/utils'

interface UseWebSocketOptions {
  url: string
  onMessage?: (message: Message) => void
  onVisualization?: (visualization: Visualization) => void
  onQualityMetrics?: (metrics: QualityMetrics) => void
  onToolCall?: (toolCall: ToolCall) => void
  onThinking?: (thinkingStep: ThinkingStep) => void
  onError?: (error: Error) => void
  onProcessGraph?: (graph: Record<string, unknown>) => void
  onTextStreamStart?: () => void
  onTextDelta?: (content: string) => void
  onTextStreamEnd?: () => void
  onSuggestions?: (suggestions: string[]) => void
  onSessionRestored?: (sessionId: string) => void
  onClarification?: (questions: ClarificationQuestion[]) => void
  onDone?: () => void
}

interface UseWebSocketReturn {
  isConnected: boolean
  isProcessing: boolean
  sendMessage: (content: string) => void
  sendRaw: (payload: Record<string, unknown>) => void
  reconnect: () => void
  newSession: () => void
  sessionId: string
}

// Backend message types (matching web_interface.py)
interface BackendMessage {
  type: 'tool_start' | 'tool_result' | 'visualization' | 'quality_metrics' | 'process_graph' | 'text' | 'done' | 'error' | 'session' | 'thinking' | 'text_stream_start' | 'text_delta' | 'text_stream_end' | 'suggestions' | 'session_restored' | 'clarification'
  tool_name?: string
  tool_input?: Record<string, unknown>
  result?: unknown
  visualization?: unknown
  metrics?: unknown
  graph?: Record<string, unknown>
  content?: string
  suggestions?: string[]
  session_id?: string
  thinking_type?: 'analyzing' | 'planning' | 'executing' | 'processing' | 'fetching' | 'validating'
  thinking_id?: string
  thinking_completed?: boolean
  questions?: ClarificationQuestion[]
}

const SESSION_KEY = 'openeo-session-id'

function getOrCreateSessionId(): string {
  const stored = localStorage.getItem(SESSION_KEY)
  if (stored) return stored
  const id = generateId()
  localStorage.setItem(SESSION_KEY, id)
  return id
}

export function useWebSocket({
  url,
  onMessage,
  onVisualization,
  onQualityMetrics,
  onToolCall,
  onThinking,
  onError,
  onProcessGraph,
  onTextStreamStart,
  onTextDelta,
  onTextStreamEnd,
  onSuggestions,
  onSessionRestored,
  onClarification,
  onDone,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId())

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const currentToolRef = useRef<{ name: string; id: string }>({ name: '', id: '' })
  const mountedRef = useRef(true)

  // Store callbacks in refs to prevent dependency issues
  const callbacksRef = useRef({
    onMessage,
    onVisualization,
    onQualityMetrics,
    onToolCall,
    onThinking,
    onError,
    onProcessGraph,
    onTextStreamStart,
    onTextDelta,
    onTextStreamEnd,
    onSuggestions,
    onSessionRestored,
    onClarification,
    onDone,
  })

  // Update callbacks ref when they change
  callbacksRef.current = {
    onMessage,
    onVisualization,
    onQualityMetrics,
    onToolCall,
    onThinking,
    onError,
    onProcessGraph,
    onTextStreamStart,
    onTextDelta,
    onTextStreamEnd,
    onSuggestions,
    onSessionRestored,
    onClarification,
    onDone,
  }

  const handleBackendMessage = useCallback((msg: BackendMessage) => {
    if (!mountedRef.current) return

    const callbacks = callbacksRef.current

    switch (msg.type) {
      case 'session':
        break

      case 'thinking': {
        const thinkingStep: ThinkingStep = {
          id: msg.thinking_id || generateId(),
          type: msg.thinking_type || 'processing',
          message: msg.content || '',
          timestamp: new Date(),
          completed: msg.thinking_completed,
        }
        callbacks.onThinking?.(thinkingStep)
        break
      }

      case 'tool_start': {
        const toolId = generateId()
        currentToolRef.current = { name: msg.tool_name || '', id: toolId }
        const toolCall: ToolCall = {
          id: toolId,
          name: msg.tool_name || 'unknown',
          arguments: msg.tool_input || {},
          status: 'running',
        }
        callbacks.onToolCall?.(toolCall)
        break
      }

      case 'tool_result': {
        const toolCall: ToolCall = {
          id: currentToolRef.current.id || generateId(),
          name: msg.tool_name || currentToolRef.current.name,
          arguments: {},
          result: msg.result,
          status: 'completed',
        }
        callbacks.onToolCall?.(toolCall)
        break
      }

      case 'visualization': {
        if (msg.visualization) {
          const viz = msg.visualization as Record<string, unknown>
          const visualization: Visualization = {
            id: generateId(),
            type: (viz.type as 'map' | 'chart' | 'comparison' | 'table' | 'process_graph') || 'map',
            title: viz.title as string,
            data: (viz.data || viz) as Visualization['data'],
          }
          callbacks.onVisualization?.(visualization)
        }
        break
      }

      case 'quality_metrics': {
        if (msg.metrics) {
          callbacks.onQualityMetrics?.(msg.metrics as QualityMetrics)
        }
        break
      }

      case 'process_graph': {
        if (msg.graph) {
          callbacks.onProcessGraph?.(msg.graph)
          const visualization: Visualization = {
            id: generateId(),
            type: 'process_graph',
            title: 'Process Graph',
            data: {
              nodes: Object.entries(msg.graph).map(([id, node]) => ({
                id,
                process_id: String((node as Record<string, unknown>).process_id || ''),
                arguments: ((node as Record<string, unknown>).arguments as Record<string, unknown>) || {},
              })),
              edges: [],
            },
          }
          callbacks.onVisualization?.(visualization)
        }
        break
      }

      case 'text_stream_start': {
        callbacks.onTextStreamStart?.()
        break
      }

      case 'text_delta': {
        callbacks.onTextDelta?.(msg.content || '')
        break
      }

      case 'text_stream_end': {
        callbacks.onTextStreamEnd?.()
        break
      }

      case 'text': {
        const message: Message = {
          id: generateId(),
          role: 'assistant',
          content: msg.content || '',
          timestamp: new Date(),
        }
        callbacks.onMessage?.(message)
        break
      }

      case 'suggestions': {
        if (msg.suggestions) {
          callbacks.onSuggestions?.(msg.suggestions)
        }
        break
      }

      case 'session_restored': {
        if (msg.session_id) {
          callbacks.onSessionRestored?.(msg.session_id)
        }
        break
      }

      case 'clarification': {
        if (msg.questions) {
          callbacks.onClarification?.(msg.questions)
        }
        break
      }

      case 'done': {
        setIsProcessing(false)
        callbacks.onDone?.()
        break
      }

      case 'error': {
        setIsProcessing(false)
        callbacks.onError?.(new Error(msg.content || 'Unknown error'))
        break
      }
    }
  }, [])

  const connect = useCallback(() => {
    // Don't connect if unmounted
    if (!mountedRef.current) return

    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = url.startsWith('ws') ? url : `${protocol}//${window.location.host}${url}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) {
          ws.close()
          return
        }
        setIsConnected(true)
        // Attempt to restore previous session
        const storedId = localStorage.getItem(SESSION_KEY)
        if (storedId) {
          ws.send(JSON.stringify({ type: 'restore_session', session_id: storedId }))
        }
      }

      ws.onclose = (event) => {
        if (!mountedRef.current) return

        setIsConnected(false)
        setIsProcessing(false)
        wsRef.current = null

        // Reconnect after delay unless it was a clean close
        if (mountedRef.current && event.code !== 1000) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              connect()
            }
          }, 2000)
        }
      }

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event)
        // onclose will handle cleanup
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const backendMessage: BackendMessage = JSON.parse(event.data)
          handleBackendMessage(backendMessage)
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error)
        }
      }
    } catch (error) {
      console.error('[WebSocket] Failed to create connection:', error)
    }
  }, [url, handleBackendMessage])

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setIsProcessing(true)
      const payload = {
        type: 'message',
        content,
        session_id: sessionId,
      }
      wsRef.current.send(JSON.stringify(payload))
    } else {
      callbacksRef.current.onError?.(new Error('WebSocket is not connected'))
    }
  }, [sessionId])

  const sendRaw = useCallback((payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    }
  }, [])

  const newSession = useCallback(() => {
    // Generate fresh session ID and clear stored one
    const newId = generateId()
    localStorage.setItem(SESSION_KEY, newId)
    setSessionId(newId)
    // Reconnect with the new session
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
    setIsProcessing(false)
    setTimeout(() => {
      if (mountedRef.current) {
        connect()
      }
    }, 100)
  }, [connect])

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current)
      connectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
    setTimeout(() => {
      if (mountedRef.current) {
        connect()
      }
    }, 100)
  }, [connect])

  useEffect(() => {
    mountedRef.current = true

    // Small delay to handle React StrictMode double-mount
    connectTimeoutRef.current = setTimeout(() => {
      if (mountedRef.current) {
        connect()
      }
    }, 100)

    return () => {
      mountedRef.current = false

      if (connectTimeoutRef.current) {
        clearTimeout(connectTimeoutRef.current)
        connectTimeoutRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close(1000, 'Component unmounting')
        wsRef.current = null
      }
    }
  }, [connect])

  return {
    isConnected,
    isProcessing,
    sendMessage,
    sendRaw,
    reconnect,
    newSession,
    sessionId,
  }
}
