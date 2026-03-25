import { useState, useEffect, useCallback } from 'react'
import { Database, MapPin, Trash2, RefreshCw, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { SavedJob } from '@/types'
import { cn, formatDateTime, formatBytes } from '@/lib/utils'

interface SavedJobsPanelProps {
  onLoadJob?: (job: SavedJob) => void
  className?: string
}

export function SavedJobsPanel({ onLoadJob, className }: SavedJobsPanelProps) {
  const [jobs, setJobs] = useState<SavedJob[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/saved-jobs?limit=50')
      if (!response.ok) throw new Error('Failed to fetch saved jobs')
      const data = await response.json()
      setJobs(data.jobs || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  const handleDelete = useCallback(async (saveId: string) => {
    try {
      await fetch(`/saved-jobs/${saveId}`, { method: 'DELETE' })
      setJobs(prev => prev.filter(j => j.save_id !== saveId))
    } catch {
      setJobs(prev => prev.filter(j => j.save_id !== saveId))
    } finally {
      setConfirmDelete(null)
    }
  }, [])

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Database className="h-4 w-4" />
            Saved Results
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={fetchJobs}
            disabled={loading}
            className="h-7 w-7"
            title="Refresh"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-4 pt-0">
        {error ? (
          <div className="py-8 text-center text-sm text-destructive">
            {error}
          </div>
        ) : jobs.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            {loading ? 'Loading...' : 'No saved results yet. Run an analysis to get started.'}
          </div>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <div
                key={job.save_id}
                className="rounded-lg border bg-card p-3 transition-colors hover:bg-muted/50"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h4 className="truncate text-sm font-medium">{job.title}</h4>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatBytes(job.size_bytes)} &middot; {job.save_id}
                    </p>
                  </div>
                  <Badge variant="outline" className="shrink-0 text-[10px]">
                    Saved
                  </Badge>
                </div>

                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(job.created_at)}
                  </span>

                  <div className="flex gap-1">
                    {onLoadJob && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onLoadJob(job)}
                        className="h-7 px-2 text-xs"
                      >
                        <MapPin className="mr-1 h-3 w-3" />
                        Load on Map
                      </Button>
                    )}
                    {confirmDelete === job.save_id ? (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setConfirmDelete(null)}
                          className="h-7 px-2 text-xs"
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(job.save_id)}
                          className="h-7 px-2 text-xs"
                        >
                          Confirm
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setConfirmDelete(job.save_id)}
                        className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
