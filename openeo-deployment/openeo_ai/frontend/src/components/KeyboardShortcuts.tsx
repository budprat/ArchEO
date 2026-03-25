import { cn } from '@/lib/utils'

interface Shortcut {
  keys: string[]
  description: string
}

const shortcuts: Shortcut[] = [
  { keys: ['Enter'], description: 'Send message' },
  { keys: ['Shift', 'Enter'], description: 'New line' },
  { keys: ['Ctrl', 'L'], description: 'Clear chat' },
  { keys: ['Ctrl', '/'], description: 'Toggle shortcuts' },
]

interface KeyboardShortcutsProps {
  className?: string
}

export function KeyboardShortcuts({ className }: KeyboardShortcutsProps) {
  return (
    <div className={cn("flex flex-col gap-2 p-3 text-sm", className)}>
      <h4 className="font-medium text-foreground">Keyboard Shortcuts</h4>
      <div className="flex flex-col gap-1.5">
        {shortcuts.map((shortcut) => (
          <div
            key={shortcut.description}
            className="flex items-center justify-between gap-4"
          >
            <span className="text-muted-foreground">{shortcut.description}</span>
            <div className="flex items-center gap-1">
              {shortcut.keys.map((key, i) => (
                <span key={i}>
                  {i > 0 && <span className="mx-0.5 text-muted-foreground">+</span>}
                  <kbd className="inline-flex items-center justify-center px-2 py-1 bg-secondary text-muted-foreground text-xs font-mono rounded border border-border tracking-widest">
                    {key}
                  </kbd>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
