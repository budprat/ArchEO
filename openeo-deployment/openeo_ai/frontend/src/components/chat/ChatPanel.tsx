import { useRef, useEffect, useState, useCallback } from 'react'
import { WifiOff, RefreshCw, Sparkles, ArrowDown, Globe, TreePine, Mountain, Cloud } from 'lucide-react'
import { Message, ThinkingStep, BBox, ClarificationQuestion } from '@/types'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { ClarificationCard } from './ClarificationCard'
import { ThinkingIndicator } from './ThinkingIndicator'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ChatPanelProps {
  messages: Message[]
  onSendMessage: (content: string) => void
  isProcessing: boolean
  isConnected: boolean
  thinkingSteps?: ThinkingStep[]
  onReconnect?: () => void
  activeBbox?: BBox | null
  onStop?: () => void
  contextSuggestions?: string[]
  pendingClarification?: ClarificationQuestion[] | null
  onClarificationSubmit?: (answers: Record<string, string | string[]>) => void
}

const SUGGESTION_CARDS = [
  {
    icon: TreePine,
    title: 'Vegetation Analysis',
    prompt: 'Show NDVI for Kerala, India during monsoon 2024 over a small area of 200x200 pixels',
    color: 'text-emerald-500',
  },
  {
    icon: Globe,
    title: 'Land Cover Change',
    prompt: 'Compare land cover changes in Amazon 2020 vs 2024 over a small area of 200x200 pixels',
    color: 'text-blue-500',
  },
  {
    icon: Mountain,
    title: 'Terrain Elevation',
    prompt: 'Analyze terrain elevation around Mount Everest over a small area of 200x200 pixels',
    color: 'text-amber-500',
  },
  {
    icon: Cloud,
    title: 'Imagery Search',
    prompt: 'Find cloud-free Sentinel-2 imagery for Paris over a small area of 200x200 pixels',
    color: 'text-violet-500',
  },
]

export function ChatPanel({
  messages,
  onSendMessage,
  isProcessing,
  isConnected,
  thinkingSteps = [],
  onReconnect,
  activeBbox,
  onStop,
  contextSuggestions = [],
  pendingClarification,
  onClarificationSubmit,
}: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const isNearBottomRef = useRef(true)

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [])

  // Auto-scroll when new messages arrive (only if near bottom)
  useEffect(() => {
    if (isNearBottomRef.current) {
      scrollToBottom()
    }
  }, [messages, thinkingSteps, scrollToBottom])

  // Track scroll position
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    const distFromBottom = scrollHeight - scrollTop - clientHeight
    isNearBottomRef.current = distFromBottom < 80
    setShowScrollBtn(distFromBottom > 200)
  }, [])


  return (
    <div className="flex h-full flex-col">
      {/* Disconnected banner */}
      {!isConnected && (
        <div className="flex items-center justify-between gap-2 border-b border-destructive/20 bg-destructive/5 px-4 py-2">
          <div className="flex items-center gap-2 text-sm text-destructive">
            <WifiOff className="h-4 w-4" />
            <span className="font-medium">Connection lost</span>
          </div>
          {onReconnect && (
            <Button
              variant="outline"
              size="sm"
              onClick={onReconnect}
              className="h-7 shrink-0 gap-1.5 border-destructive/20 text-destructive hover:bg-destructive/5"
            >
              <RefreshCw className="h-3 w-3" />
              Reconnect
            </Button>
          )}
        </div>
      )}

      {/* Messages area */}
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto"
        >
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center px-6 py-12">
              {/* Logo */}
              <div className="animate-float mb-6">
                <img
                  src="/jonaai.png"
                  alt="Jona AI"
                  className="h-16 w-auto drop-shadow-md dark:invert"
                />
              </div>

              <h2 className="mb-2 text-xl font-semibold tracking-tight">
                Jona AI Assistant
              </h2>
              <p className="mb-8 max-w-[300px] text-center text-sm leading-relaxed text-muted-foreground">
                Analyze Earth observation data using natural language.
              </p>

              {/* Suggestion cards grid */}
              <div className="grid w-full max-w-[340px] grid-cols-2 gap-2">
                {SUGGESTION_CARDS.map((card, index) => (
                  <button
                    key={index}
                    onClick={() => onSendMessage(card.prompt)}
                    className="stagger-enter group flex flex-col gap-2 rounded-xl border border-border/60 bg-card p-3 text-left transition-all duration-200 hover:border-primary/30 hover:bg-primary/[0.02] hover:shadow-sm active:scale-[0.98]"
                    style={{ animationDelay: `${index * 80}ms` }}
                  >
                    <card.icon className={cn("h-4 w-4", card.color)} />
                    <span className="text-xs font-medium text-foreground">{card.title}</span>
                    <span className="text-[11px] leading-tight text-muted-foreground/70 line-clamp-2">
                      {card.prompt}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="py-2">
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}

              {/* Clarification card */}
              {pendingClarification && onClarificationSubmit && (
                <ClarificationCard
                  questions={pendingClarification}
                  onSubmit={onClarificationSubmit}
                />
              )}

              {/* Thinking indicator */}
              {(isProcessing || thinkingSteps.length > 0) && (
                <div className="flex gap-3 px-4 py-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/5">
                    <Sparkles className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <div className="flex-1 pt-0.5">
                    <ThinkingIndicator steps={thinkingSteps} isProcessing={isProcessing} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full border border-border bg-background/95 px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-lg backdrop-blur-sm transition-all hover:bg-muted hover:text-foreground"
          >
            <ArrowDown className="h-3 w-3" />
            Scroll to bottom
          </button>
        )}
      </div>

      <ChatInput
        onSend={onSendMessage}
        isProcessing={isProcessing}
        disabled={!isConnected}
        placeholder={
          !isConnected
            ? 'Connecting to server...'
            : 'Ask about Earth observation data...'
        }
        activeBbox={activeBbox}
        onStop={onStop}
        contextSuggestions={contextSuggestions}
      />
    </div>
  )
}
