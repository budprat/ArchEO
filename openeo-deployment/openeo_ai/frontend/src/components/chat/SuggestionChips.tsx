import { cn } from '@/lib/utils'

interface SuggestionChipsProps {
  suggestions: string[]
  onSelect: (suggestion: string) => void
  maxLength?: number
  className?: string
}

export function SuggestionChips({
  suggestions,
  onSelect,
  maxLength = 40,
  className,
}: SuggestionChipsProps) {
  return (
    <div className={cn("mb-3 flex gap-2 overflow-x-auto", className)} style={{ scrollbarWidth: 'none', msOverflowStyle: 'none', WebkitOverflowScrolling: 'touch' }}>
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          onClick={() => onSelect(suggestion)}
          className="stagger-enter shrink-0 rounded-full bg-secondary/80 px-3.5 py-1.5 text-[13px] font-normal text-muted-foreground transition-all duration-200 cursor-pointer border border-transparent hover:border-primary/20 hover:bg-primary/5 hover:text-foreground hover:shadow-sm active:scale-[0.97] whitespace-nowrap"
          style={{ animationDelay: `${index * 60}ms` }}
        >
          {suggestion.length > maxLength
            ? `${suggestion.slice(0, maxLength)}...`
            : suggestion}
        </button>
      ))}
    </div>
  )
}
