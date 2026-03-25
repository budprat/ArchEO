/**
 * useCodeExecution Hook
 *
 * Provides code execution with result parsing for visualizations.
 * Handles graph output, result display, and error formatting.
 */

import { useState, useCallback } from 'react'
import { usePyodide } from '../contexts/pyodide-context'
import { Visualization } from '../types'

interface ExecutionState {
  running: boolean
  output: string
  error: string | null
  executionTime: number | null
  visualizations: Visualization[]
}

interface UseCodeExecutionReturn extends ExecutionState {
  execute: (code: string) => Promise<void>
  clear: () => void
  isReady: boolean
  loadProgress: number
}

// Parse special output markers from Python stdout
function parseSpecialOutputs(stdout: string): {
  cleanOutput: string
  visualizations: Visualization[]
} {
  const lines = stdout.split('\n')
  const visualizations: Visualization[] = []
  const cleanLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('__GRAPH_OUTPUT__:')) {
      try {
        const data = JSON.parse(line.slice('__GRAPH_OUTPUT__:'.length))
        visualizations.push({
          id: `graph-${Date.now()}`,
          type: 'process_graph',
          title: data.title || 'Process Graph',
          data: {
            nodes: parseGraphNodes(data.graph),
            edges: parseGraphEdges(data.graph),
          },
        })
      } catch (e) {
        console.error('Failed to parse graph output:', e)
        cleanLines.push(line)
      }
    } else if (line.startsWith('__RESULT_OUTPUT__:')) {
      try {
        const data = JSON.parse(line.slice('__RESULT_OUTPUT__:'.length))
        if (Array.isArray(data.data)) {
          // Array data - create chart visualization
          visualizations.push({
            id: `chart-${Date.now()}`,
            type: 'chart',
            title: data.title || 'Result',
            data: {
              chartType: 'line',
              title: data.title || 'Result',
              xAxis: {
                label: 'Index',
                values: data.data.map((_: any, i: number) => i),
              },
              yAxis: {
                label: 'Value',
              },
              series: [{ name: 'Values', values: data.data }],
            },
          })
        } else {
          // Other data - show as table
          visualizations.push({
            id: `table-${Date.now()}`,
            type: 'table',
            title: data.title || 'Result',
            data: {
              headers: Object.keys(data.data || {}),
              rows: [Object.values(data.data || {}) as (string | number)[]],
            },
          })
        }
      } catch (e) {
        console.error('Failed to parse result output:', e)
        cleanLines.push(line)
      }
    } else {
      cleanLines.push(line)
    }
  }

  return {
    cleanOutput: cleanLines.join('\n'),
    visualizations,
  }
}

// Parse OpenEO process graph nodes
function parseGraphNodes(graph: Record<string, any>): any[] {
  if (!graph || typeof graph !== 'object') return []

  return Object.entries(graph).map(([id, node]) => ({
    id,
    process_id: node.process_id || id,
    arguments: node.arguments || {},
    result: node.result || false,
  }))
}

// Parse OpenEO process graph edges
function parseGraphEdges(graph: Record<string, any>): any[] {
  if (!graph || typeof graph !== 'object') return []

  const edges: any[] = []

  const findReferences = (obj: any, nodeId: string, argName: string) => {
    if (!obj || typeof obj !== 'object') return

    if ('from_node' in obj) {
      edges.push({
        source: obj.from_node,
        target: nodeId,
        argument: argName,
      })
    }

    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === 'object' && value !== null) {
        findReferences(value, nodeId, key)
      }
    }
  }

  for (const [nodeId, node] of Object.entries(graph)) {
    if (node && typeof node === 'object' && 'arguments' in node) {
      findReferences(node.arguments, nodeId, 'data')
    }
  }

  return edges
}

export function useCodeExecution(): UseCodeExecutionReturn {
  const { runPython, ready, loadProgress } = usePyodide()

  const [state, setState] = useState<ExecutionState>({
    running: false,
    output: '',
    error: null,
    executionTime: null,
    visualizations: [],
  })

  const execute = useCallback(
    async (code: string) => {
      setState((prev) => ({
        ...prev,
        running: true,
        error: null,
        output: '',
        visualizations: [],
      }))

      try {
        const result = await runPython(code)

        const { cleanOutput, visualizations } = parseSpecialOutputs(result.stdout)

        if (result.success) {
          // Format output
          let output = cleanOutput

          // Add result if not already captured
          if (result.output !== undefined && result.output !== null) {
            const outputStr =
              typeof result.output === 'object'
                ? JSON.stringify(result.output, null, 2)
                : String(result.output)

            if (outputStr && outputStr !== 'None') {
              output = output ? `${output}\n\n→ ${outputStr}` : `→ ${outputStr}`
            }
          }

          setState({
            running: false,
            output: output.trim(),
            error: null,
            executionTime: result.executionTime,
            visualizations,
          })
        } else {
          setState({
            running: false,
            output: cleanOutput,
            error: result.stderr,
            executionTime: result.executionTime,
            visualizations: [],
          })
        }
      } catch (err) {
        setState({
          running: false,
          output: '',
          error: err instanceof Error ? err.message : 'Execution failed',
          executionTime: null,
          visualizations: [],
        })
      }
    },
    [runPython]
  )

  const clear = useCallback(() => {
    setState({
      running: false,
      output: '',
      error: null,
      executionTime: null,
      visualizations: [],
    })
  }, [])

  return {
    ...state,
    execute,
    clear,
    isReady: ready,
    loadProgress,
  }
}

export default useCodeExecution
