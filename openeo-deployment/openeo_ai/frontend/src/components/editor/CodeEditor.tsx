/**
 * Code Editor Component
 *
 * Python code editor with CodeMirror, AI assist, and execution.
 * Supports syntax highlighting, autocompletion, and result display.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { Play, Loader2, Sparkles, Trash2, Copy, Check, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useCodeExecution } from '@/hooks/useCodeExecution'
import { usePyodide } from '@/contexts/pyodide-context'
import { cn } from '@/lib/utils'

interface CodeEditorProps {
  initialCode?: string
  onExecute?: (code: string, result: any) => void
  onAiAssist?: (code: string, selection: string) => Promise<string>
  className?: string
}

// Default example code
const DEFAULT_CODE = `# OpenEO Python Example
# This code runs in your browser via Pyodide (WebAssembly)

import numpy as np

# Create sample NDVI data
dates = ['2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06']
ndvi_values = [0.35, 0.42, 0.58, 0.72, 0.68, 0.55]

# Display as array
data = array_create(ndvi_values)
print(f"NDVI values: {data}")
print(f"Mean NDVI: {np.mean(data):.3f}")
print(f"Max NDVI: {np.max(data):.3f}")

# Show result visualization
show_result(ndvi_values, "Monthly NDVI")

# Example process graph (for visualization)
graph = {
    "load1": {
        "process_id": "load_collection",
        "arguments": {
            "id": "sentinel-2-l2a",
            "bands": ["red", "nir"]
        }
    },
    "ndvi1": {
        "process_id": "ndvi",
        "arguments": {
            "data": {"from_node": "load1"}
        },
        "result": True
    }
}
add_graph_to_map(graph, "NDVI Calculation")
`

export function CodeEditor({
  initialCode = DEFAULT_CODE,
  onExecute,
  onAiAssist,
  className,
}: CodeEditorProps) {
  const [code, setCode] = useState(initialCode)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState('output')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { execute, running, output, error, executionTime, visualizations, isReady, loadProgress } =
    useCodeExecution()
  const { loading: pyodideLoading } = usePyodide()

  // Handle code execution
  const handleRun = useCallback(async () => {
    await execute(code)
    if (onExecute) {
      onExecute(code, { output, error, visualizations })
    }
  }, [code, execute, onExecute, output, error, visualizations])

  // Handle AI assist (placeholder for Claude integration)
  const handleAiAssist = useCallback(async () => {
    if (!onAiAssist) return

    const textarea = textareaRef.current
    if (!textarea) return

    const selection = textarea.value.substring(textarea.selectionStart, textarea.selectionEnd)
    const suggestion = await onAiAssist(code, selection || code)

    if (suggestion) {
      setCode(suggestion)
    }
  }, [code, onAiAssist])

  // Handle copy
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [code])

  // Handle clear
  const handleClear = useCallback(() => {
    setCode('')
  }, [])

  // Handle download
  const handleDownload = useCallback(() => {
    const blob = new Blob([code], { type: 'text/x-python' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'openeo_script.py'
    a.click()
    URL.revokeObjectURL(url)
  }, [code])

  // Keyboard shortcut: Ctrl/Cmd + Enter to run
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleRun()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleRun])

  // Auto-switch to output tab when execution completes
  useEffect(() => {
    if (output || error) {
      setActiveTab('output')
    }
    if (visualizations.length > 0) {
      setActiveTab('visualizations')
    }
  }, [output, error, visualizations])

  return (
    <Card className={cn('flex h-full flex-col', className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">Python Editor</CardTitle>
            {pyodideLoading && (
              <Badge variant="secondary" className="text-xs">
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                Loading Pyodide ({loadProgress}%)
              </Badge>
            )}
            {isReady && (
              <Badge variant="success" className="text-xs">
                Ready
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleCopy}
              title="Copy code"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleDownload}
              title="Download as .py"
            >
              <Download className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleClear}
              title="Clear code"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
            {onAiAssist && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={handleAiAssist}
                disabled={!isReady}
              >
                <Sparkles className="h-4 w-4" />
                AI Assist
              </Button>
            )}
            <Button
              variant="default"
              size="sm"
              className="gap-1"
              onClick={handleRun}
              disabled={running || !isReady}
            >
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-2 overflow-hidden p-4">
        {/* Code input */}
        <div className="flex-1 overflow-hidden rounded-md border">
          <textarea
            ref={textareaRef}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="h-full w-full resize-none bg-foreground text-background p-4 font-mono text-sm focus:outline-none"
            placeholder="# Enter Python code here..."
            spellCheck={false}
          />
        </div>

        {/* Output panel */}
        <div className="h-1/3 min-h-[150px] overflow-hidden">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex h-full flex-col">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="output" className="text-xs">
                Output
                {executionTime !== null && (
                  <span className="ml-1 text-muted-foreground">({executionTime.toFixed(0)}ms)</span>
                )}
              </TabsTrigger>
              <TabsTrigger value="visualizations" className="text-xs">
                Visualizations
                {visualizations.length > 0 && (
                  <Badge variant="secondary" className="ml-1">
                    {visualizations.length}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="help" className="text-xs">
                Help
              </TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-hidden">
              <TabsContent value="output" className="m-0 h-full overflow-auto">
                <div className="h-full rounded-md bg-foreground/5 p-3 font-mono text-sm">
                  {error ? (
                    <pre className="text-destructive">{error}</pre>
                  ) : output ? (
                    <pre className="whitespace-pre-wrap">{output}</pre>
                  ) : (
                    <span className="text-muted-foreground">
                      Press Run (or Ctrl+Enter) to execute code
                    </span>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="visualizations" className="m-0 h-full overflow-auto">
                <div className="h-full rounded-md bg-foreground/5 p-3">
                  {visualizations.length > 0 ? (
                    <div className="space-y-2">
                      {visualizations.map((viz, i) => (
                        <div key={i} className="rounded border bg-card p-2">
                          <div className="mb-1 text-xs font-medium">{viz.title}</div>
                          <pre className="text-xs text-muted-foreground">
                            {JSON.stringify(viz.data, null, 2).slice(0, 500)}
                            {JSON.stringify(viz.data).length > 500 && '...'}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-muted-foreground text-sm">
                      Use show_result() or add_graph_to_map() to create visualizations
                    </span>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="help" className="m-0 h-full overflow-auto">
                <div className="h-full rounded-md bg-foreground/5 p-3 text-sm">
                  <div className="space-y-2">
                    <div>
                      <strong>Available Functions:</strong>
                    </div>
                    <ul className="space-y-1 pl-4 text-muted-foreground">
                      <li>
                        <code>array_create(data)</code> - Create a numpy array
                      </li>
                      <li>
                        <code>datacube(data, dims, coords)</code> - Create a DataCube
                      </li>
                      <li>
                        <code>show_result(data, title)</code> - Display result visualization
                      </li>
                      <li>
                        <code>add_graph_to_map(graph, title)</code> - Show process graph
                      </li>
                    </ul>
                    <div className="mt-2">
                      <strong>Available Packages:</strong>
                    </div>
                    <ul className="space-y-1 pl-4 text-muted-foreground">
                      <li>
                        <code>numpy</code> (as np)
                      </li>
                      <li>
                        <code>json</code>, <code>math</code>, <code>statistics</code>
                      </li>
                    </ul>
                    <div className="mt-2">
                      <strong>Keyboard Shortcuts:</strong>
                    </div>
                    <ul className="space-y-1 pl-4 text-muted-foreground">
                      <li>
                        <code>Ctrl+Enter</code> - Run code
                      </li>
                    </ul>
                  </div>
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </CardContent>
    </Card>
  )
}

export default CodeEditor
