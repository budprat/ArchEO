import { useState, useCallback } from 'react'
import { FolderOpen, Plus, Trash2, Check, X, PenLine } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { Project } from '@/types'
import { cn } from '@/lib/utils'

interface ProjectsPanelProps {
  projects: Project[]
  activeProjectId: string | null
  onSelectProject: (project: Project) => void
  onCreateProject: (name: string, description: string) => void
  onDeleteProject: (id: string) => void
  onRenameProject: (id: string, name: string) => void
  className?: string
}

export function ProjectsPanel({
  projects,
  activeProjectId,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
  onRenameProject,
  className,
}: ProjectsPanelProps) {
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  const handleCreate = useCallback(() => {
    const name = newName.trim()
    if (!name) return
    onCreateProject(name, newDesc.trim())
    setNewName('')
    setNewDesc('')
    setCreating(false)
  }, [newName, newDesc, onCreateProject])

  const handleRename = useCallback((id: string) => {
    const name = editName.trim()
    if (!name) return
    onRenameProject(id, name)
    setEditingId(null)
  }, [editName, onRenameProject])

  return (
    <Card className={cn("flex flex-col border-0 shadow-none", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
            Projects
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCreating(true)}
            className="h-7 w-7"
            title="New Project"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-4 pt-0">
        {/* Create form */}
        {creating && (
          <div className="mb-3 rounded-lg border bg-muted/30 p-3 space-y-2">
            <input
              autoFocus
              type="text"
              placeholder="Project name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              className="w-full rounded-md border bg-background px-2.5 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              className="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
            />
            <div className="flex justify-end gap-1">
              <Button variant="ghost" size="sm" onClick={() => setCreating(false)} className="h-7 px-2 text-xs">
                Cancel
              </Button>
              <Button size="sm" onClick={handleCreate} disabled={!newName.trim()} className="h-7 px-2 text-xs">
                Create
              </Button>
            </div>
          </div>
        )}

        {projects.length === 0 && !creating ? (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="mb-3 rounded-xl bg-muted/50 p-3">
              <FolderOpen className="h-6 w-6 text-muted-foreground/50" />
            </div>
            <p className="text-sm text-muted-foreground">No projects yet</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3 text-xs"
              onClick={() => setCreating(true)}
            >
              <Plus className="mr-1 h-3 w-3" />
              Create Project
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => onSelectProject(project)}
                className={cn(
                  "cursor-pointer rounded-lg border p-3 transition-colors hover:bg-muted/50",
                  activeProjectId === project.id && "border-primary/50 bg-primary/5"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    {editingId === project.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          autoFocus
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleRename(project.id)
                            if (e.key === 'Escape') setEditingId(null)
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="w-full rounded border bg-background px-1.5 py-0.5 text-sm outline-none focus:ring-1 focus:ring-ring"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 shrink-0"
                          onClick={(e) => { e.stopPropagation(); handleRename(project.id) }}
                        >
                          <Check className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 shrink-0"
                          onClick={(e) => { e.stopPropagation(); setEditingId(null) }}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ) : (
                      <h4 className="truncate text-sm font-medium">{project.name}</h4>
                    )}
                    {project.description && editingId !== project.id && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">{project.description}</p>
                    )}
                  </div>
                  {activeProjectId === project.id && editingId !== project.id && (
                    <Badge variant="default" className="shrink-0 text-[10px]">Active</Badge>
                  )}
                </div>

                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">
                    {project.analysisCount} {project.analysisCount === 1 ? 'analysis' : 'analyses'}
                  </span>
                  <div className="flex gap-0.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      title="Rename"
                      onClick={(e) => {
                        e.stopPropagation()
                        setEditingId(project.id)
                        setEditName(project.name)
                      }}
                    >
                      <PenLine className="h-3 w-3" />
                    </Button>
                    {confirmDelete === project.id ? (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-1.5 text-[10px]"
                          onClick={(e) => { e.stopPropagation(); setConfirmDelete(null) }}
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          className="h-6 px-1.5 text-[10px]"
                          onClick={(e) => {
                            e.stopPropagation()
                            onDeleteProject(project.id)
                            setConfirmDelete(null)
                          }}
                        >
                          Delete
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-destructive hover:text-destructive"
                        title="Delete"
                        onClick={(e) => { e.stopPropagation(); setConfirmDelete(project.id) }}
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
