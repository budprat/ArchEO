import { useState, useEffect, useRef } from 'react'
import { Brain, ChevronDown, ChevronRight, Search, Cog, Database, CheckCircle, Loader2 } from 'lucide-react'
import { ThinkingStep } from '@/types'
import { cn } from '@/lib/utils'

interface ThinkingIndicatorProps {
  steps: ThinkingStep[]
  isProcessing: boolean
}

const stepIcons = {
  analyzing: Brain,
  planning: Cog,
  executing: Loader2,
  processing: Cog,
  fetching: Database,
  validating: Search,
}

const stepLabels = {
  analyzing: 'Analyzing',
  planning: 'Planning',
  executing: 'Executing',
  processing: 'Processing',
  fetching: 'Fetching data',
  validating: 'Validating',
}

export function ThinkingIndicator({ steps, isProcessing }: ThinkingIndicatorProps) {
  const [expanded, setExpanded] = useState(true)
  const [elapsed, setElapsed] = useState(0)
  const startTimeRef = useRef<number>(Date.now())

  useEffect(() => {
    startTimeRef.current = Date.now()
    setElapsed(0)
  }, [])

  useEffect(() => {
    if (!isProcessing && steps.length === 0) return

    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000))
    }, 1000)

    return () => clearInterval(interval)
  }, [isProcessing, steps.length])

  if (steps.length === 0 && !isProcessing) {
    return null
  }

  const activeSteps = steps.filter(s => !s.completed)
  const latestStep = activeSteps[activeSteps.length - 1] || steps[steps.length - 1]

  return (
    <div className="mb-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted/50 transition-colors"
      >
        {isProcessing ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
        ) : (
          <Brain className="h-3.5 w-3.5 text-primary" />
        )}

        <span className="font-medium">
          {isProcessing ? (
            <>Thinking{elapsed > 0 ? ` for ${elapsed}s` : '...'}</>
          ) : (
            <>Thought for {elapsed}s</>
          )}
        </span>

        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <>
            {latestStep && (
              <span className="text-muted-foreground/60 truncate max-w-[200px]">
                - {latestStep.message}
              </span>
            )}
            <ChevronRight className="h-3 w-3" />
          </>
        )}
      </button>

      {expanded && (
        <div className="ml-2 mt-1 border-l-2 border-border pl-4 pb-1">
          <div className="flex flex-col gap-1.5">
            {steps.map((step, index) => {
              const Icon = stepIcons[step.type] || Cog
              const label = stepLabels[step.type] || step.type

              return (
                <div
                  key={step.id}
                  className={cn(
                    "stagger-enter flex items-start gap-2 text-xs",
                    step.completed ? "text-muted-foreground/40" : "text-muted-foreground"
                  )}
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  {step.completed ? (
                    <CheckCircle className="mt-0.5 h-3 w-3 shrink-0 text-success/60" />
                  ) : (
                    <Icon className="mt-0.5 h-3 w-3 shrink-0 text-primary animate-spin" />
                  )}
                  <span>
                    <span className="font-medium">{label}:</span>{' '}
                    <span className="text-muted-foreground/70">{step.message}</span>
                  </span>
                </div>
              )
            })}

            {isProcessing && steps.length === 0 && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground/60">
                <Loader2 className="h-3 w-3 animate-spin text-primary" />
                <span>Starting...</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
