import { Settings, HelpCircle, Moon, Sun, Wifi, WifiOff, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface HeaderProps {
  isConnected: boolean
  isDark?: boolean
  onToggleTheme?: () => void
  onHelp?: () => void
  onSettings?: () => void
  onNewChat?: () => void
}

export function Header({
  isConnected,
  isDark = false,
  onToggleTheme,
  onHelp,
  onSettings,
  onNewChat,
}: HeaderProps) {
  return (
    <header className="glass sticky top-0 z-50 flex h-16 items-center justify-between px-5">
      <div className="flex items-center gap-3">
        <div className="group flex items-center gap-2.5 cursor-pointer select-none">
          <div className="relative animate-logo-enter">
            <img
              src="/jonaai.png"
              alt="Jona AI"
              className="h-10 w-auto drop-shadow-sm transition-all duration-300 group-hover:scale-110 group-hover:drop-shadow-md dark:invert"
            />
            <div className="absolute inset-0 rounded-full bg-primary/0 transition-all duration-300 group-hover:bg-primary/10 group-hover:blur-xl" />
          </div>
          <span className="animate-logo-enter text-lg font-semibold tracking-tight opacity-0 [animation-delay:150ms]">
            Jona AI
          </span>
        </div>
        <Badge variant="outline" className="animate-logo-enter text-[10px] font-medium uppercase tracking-widest opacity-0 [animation-delay:300ms]">
          v0.2.0
        </Badge>
      </div>

      <div className="flex items-center gap-1.5">
        <Badge
          variant={isConnected ? 'success' : 'destructive'}
          className={cn(
            "flex items-center gap-1.5 transition-all duration-300",
            isConnected ? 'bg-success pulse-ring' : 'bg-destructive'
          )}
        >
          {isConnected ? (
            <>
              <Wifi className="h-3 w-3" />
              <span className="text-[10px] font-medium uppercase tracking-wider">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3" />
              <span className="text-[10px] font-medium uppercase tracking-wider">Offline</span>
            </>
          )}
        </Badge>

        <div className="ml-1 flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={onNewChat}
            className="h-9 gap-1.5 rounded-lg px-3 text-muted-foreground transition-colors hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
            <span className="text-xs font-medium">New Chat</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleTheme}
            className="h-9 w-9 rounded-lg text-muted-foreground transition-colors hover:text-foreground"
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onHelp}
            className="h-9 w-9 rounded-lg text-muted-foreground transition-colors hover:text-foreground"
          >
            <HelpCircle className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onSettings}
            className="h-9 w-9 rounded-lg text-muted-foreground transition-colors hover:text-foreground"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
