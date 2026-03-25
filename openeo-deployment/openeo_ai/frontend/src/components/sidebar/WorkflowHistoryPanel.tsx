import { History, Play, CheckCircle2, XCircle, Clock, RotateCcw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Workflow } from '@/types'
import { cn, formatDateTime } from '@/lib/utils'

interface WorkflowHistoryPanelProps {
  workflows: Workflow[]
  onReplay?: (workflow: Workflow) => void
  className?: string
}

export function WorkflowHistoryPanel({
  workflows,
  onReplay,
  className,
}: WorkflowHistoryPanelProps) {
  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <History className="h-4 w-4" />
          Workflow History
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        <ScrollArea className="h-full">
          {workflows.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No workflows yet. Start by asking a question.
            </div>
          ) : (
            <div className="space-y-2 p-4">
              {workflows.map((workflow) => (
                <WorkflowItem
                  key={workflow.id}
                  workflow={workflow}
                  onReplay={onReplay}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

function WorkflowItem({
  workflow,
  onReplay,
}: {
  workflow: Workflow
  onReplay?: (workflow: Workflow) => void
}) {
  const statusConfig = {
    idle: { icon: Clock, color: 'bg-muted text-muted-foreground', label: 'Idle' },
    running: { icon: Play, color: 'bg-blue-500/15 text-blue-700 dark:text-blue-400', label: 'Running' },
    completed: { icon: CheckCircle2, color: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400', label: 'Completed' },
    error: { icon: XCircle, color: 'bg-red-500/15 text-red-700 dark:text-red-400', label: 'Error' },
  }

  const status = statusConfig[workflow.status]
  const StatusIcon = status.icon

  return (
    <div className="rounded-lg border bg-card p-3 transition-colors hover:bg-muted/50">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h4 className="truncate text-sm font-medium">{workflow.name}</h4>
          {workflow.description && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {workflow.description}
            </p>
          )}
        </div>
        <Badge variant="outline" className={cn("shrink-0 text-xs", status.color)}>
          <StatusIcon className="mr-1 h-3 w-3" />
          {status.label}
        </Badge>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {formatDateTime(workflow.createdAt)}
        </span>

        {workflow.status === 'completed' && onReplay && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onReplay(workflow)}
            className="h-7 px-2 text-xs"
          >
            <RotateCcw className="mr-1 h-3 w-3" />
            Replay
          </Button>
        )}
      </div>

      {workflow.steps.length > 0 && (
        <div className="mt-2 border-t pt-2">
          <div className="flex flex-wrap gap-1">
            {workflow.steps.slice(0, 3).map((step) => (
              <span
                key={step.id}
                className={cn(
                  "rounded px-1.5 py-0.5 text-xs",
                  step.status === 'completed'
                    ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                    : step.status === 'error'
                    ? 'bg-red-500/15 text-red-700 dark:text-red-400'
                    : step.status === 'running'
                    ? 'bg-blue-500/15 text-blue-700 dark:text-blue-400'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {step.name}
              </span>
            ))}
            {workflow.steps.length > 3 && (
              <span className="text-xs text-muted-foreground">
                +{workflow.steps.length - 3} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
