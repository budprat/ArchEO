import { useState } from 'react'
import { HelpCircle, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ClarificationQuestion } from '@/types'
import { cn } from '@/lib/utils'

interface ClarificationCardProps {
  questions: ClarificationQuestion[]
  onSubmit: (answers: Record<string, string | string[]>) => void
}

export function ClarificationCard({ questions, onSubmit }: ClarificationCardProps) {
  const [selections, setSelections] = useState<Record<string, string | string[]>>({})
  const [submitted, setSubmitted] = useState(false)

  const handleSelect = (questionIdx: number, label: string, multiSelect?: boolean) => {
    const key = String(questionIdx)
    if (multiSelect) {
      const current = (selections[key] as string[]) || []
      const next = current.includes(label)
        ? current.filter((l) => l !== label)
        : [...current, label]
      setSelections((prev) => ({ ...prev, [key]: next }))
    } else {
      setSelections((prev) => ({ ...prev, [key]: label }))
    }
  }

  const handleSubmit = () => {
    setSubmitted(true)
    onSubmit(selections)
  }

  const allAnswered = questions.every((_, idx) => {
    const val = selections[String(idx)]
    if (Array.isArray(val)) return val.length > 0
    return !!val
  })

  return (
    <div className={cn(
      "mx-4 my-2 rounded-xl border bg-card p-4 shadow-sm transition-opacity",
      submitted && "opacity-60"
    )}>
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-primary">
        <HelpCircle className="h-4 w-4" />
        <span>Clarification needed</span>
      </div>

      <div className="space-y-4">
        {questions.map((q, qIdx) => (
          <div key={qIdx}>
            <p className="mb-2 text-sm font-medium">{q.question}</p>
            <div className="flex flex-wrap gap-2">
              {q.options.map((opt) => {
                const key = String(qIdx)
                const isSelected = q.multiSelect
                  ? ((selections[key] as string[]) || []).includes(opt.label)
                  : selections[key] === opt.label

                return (
                  <button
                    key={opt.label}
                    disabled={submitted}
                    onClick={() => handleSelect(qIdx, opt.label, q.multiSelect)}
                    className={cn(
                      "group relative rounded-lg border px-3 py-2 text-left text-xs transition-all",
                      "hover:border-primary/40 hover:bg-primary/5",
                      isSelected
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border/60 text-muted-foreground",
                      submitted && "cursor-not-allowed"
                    )}
                  >
                    <span className="font-medium">{opt.label}</span>
                    {opt.description && (
                      <span className="ml-1 text-muted-foreground/70">
                        — {opt.description}
                      </span>
                    )}
                    {isSelected && (
                      <Check className="absolute -right-1 -top-1 h-3.5 w-3.5 rounded-full bg-primary p-0.5 text-primary-foreground" />
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {!submitted && (
        <div className="mt-3 flex justify-end">
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!allAnswered}
            className="h-8 text-xs"
          >
            Submit
          </Button>
        </div>
      )}

      {submitted && (
        <p className="mt-2 text-xs text-muted-foreground">Answers submitted — processing...</p>
      )}
    </div>
  )
}
