/**
 * Pyodide Context Provider
 *
 * Provides in-browser Python execution via Pyodide (WebAssembly).
 * Includes CDN loading, micropip support, and OpenEO builtins.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'

// Type declarations for Pyodide
declare global {
  interface Window {
    loadPyodide: (config?: { indexURL?: string }) => Promise<PyodideInterface>
  }
}

interface PyodideInterface {
  runPython: (code: string) => any
  runPythonAsync: (code: string) => Promise<any>
  loadPackage: (packages: string | string[]) => Promise<void>
  micropip: {
    install: (packages: string | string[]) => Promise<void>
  }
  globals: any
  FS: {
    writeFile: (path: string, data: string | Uint8Array) => void
    readFile: (path: string, opts?: { encoding: string }) => string | Uint8Array
    mkdir: (path: string) => void
  }
  pyimport: (module: string) => any
  toPy: (obj: any) => any
  toJs: (obj: any) => any
}

interface ExecutionResult {
  success: boolean
  output: any
  stdout: string
  stderr: string
  executionTime: number
}

interface PyodideContextType {
  pyodide: PyodideInterface | null
  loading: boolean
  loadProgress: number
  error: string | null
  ready: boolean
  runPython: (code: string) => Promise<ExecutionResult>
  installPackage: (packages: string | string[]) => Promise<void>
  loadedPackages: string[]
}

const PyodideContext = createContext<PyodideContextType | null>(null)

// CDN URL for Pyodide
const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/'

// Default packages to load
const DEFAULT_PACKAGES = ['numpy', 'micropip']

// OpenEO builtins to inject
const OPENEO_BUILTINS = `
# OpenEO Python Builtins for in-browser execution
import json

class DataCube:
    """Mock DataCube for in-browser visualization."""
    def __init__(self, data=None, dims=None, coords=None):
        self.data = data
        self.dims = dims or []
        self.coords = coords or {}
        self._graph = {}

    def __repr__(self):
        return f"DataCube(dims={self.dims})"

    def to_dict(self):
        return {"type": "datacube", "dims": self.dims, "coords": self.coords}

def array_create(data):
    """Create an array from data."""
    import numpy as np
    return np.array(data)

def datacube(data, dims=None, coords=None):
    """Create a DataCube object."""
    return DataCube(data, dims, coords)

def add_graph_to_map(graph, title="Process Graph"):
    """Signal to add graph visualization to map."""
    print(f"__GRAPH_OUTPUT__:{json.dumps({'type': 'process_graph', 'title': title, 'graph': graph})}")
    return graph

def show_result(data, title="Result"):
    """Signal to show result in visualization panel."""
    if hasattr(data, 'tolist'):
        data = data.tolist()
    elif hasattr(data, 'to_dict'):
        data = data.to_dict()
    print(f"__RESULT_OUTPUT__:{json.dumps({'type': 'result', 'title': title, 'data': data})}")
    return data

# Make builtins available
__builtins__['DataCube'] = DataCube
__builtins__['array_create'] = array_create
__builtins__['datacube'] = datacube
__builtins__['add_graph_to_map'] = add_graph_to_map
__builtins__['show_result'] = show_result
`

interface PyodideProviderProps {
  children: React.ReactNode
  autoLoad?: boolean
}

export function PyodideProvider({ children, autoLoad = false }: PyodideProviderProps) {
  const [pyodide, setPyodide] = useState<PyodideInterface | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadProgress, setLoadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [loadedPackages, setLoadedPackages] = useState<string[]>([])


  // Load Pyodide from CDN
  const loadPyodide = useCallback(async () => {
    if (pyodide || loading) return

    setLoading(true)
    setLoadProgress(0)
    setError(null)

    try {
      // Load Pyodide script
      setLoadProgress(10)

      if (!window.loadPyodide) {
        const script = document.createElement('script')
        script.src = `${PYODIDE_CDN}pyodide.js`
        script.async = true

        await new Promise<void>((resolve, reject) => {
          script.onload = () => resolve()
          script.onerror = () => reject(new Error('Failed to load Pyodide script'))
          document.head.appendChild(script)
        })
      }

      setLoadProgress(30)

      // Initialize Pyodide
      const pyodideInstance = await window.loadPyodide({
        indexURL: PYODIDE_CDN,
      })

      setLoadProgress(60)

      // Load default packages
      await pyodideInstance.loadPackage(DEFAULT_PACKAGES)
      setLoadedPackages([...DEFAULT_PACKAGES])

      setLoadProgress(80)

      // Set up stdout/stderr capture
      pyodideInstance.runPython(`
import sys
from io import StringIO

class StdoutCapture:
    def __init__(self):
        self.buffer = []
    def write(self, text):
        self.buffer.append(text)
    def flush(self):
        pass
    def getvalue(self):
        return ''.join(self.buffer)
    def clear(self):
        self.buffer = []

sys.stdout = StdoutCapture()
sys.stderr = StdoutCapture()
`)

      // Inject OpenEO builtins
      pyodideInstance.runPython(OPENEO_BUILTINS)

      setLoadProgress(100)
      setPyodide(pyodideInstance)
      setReady(true)

      console.log('[Pyodide] Initialized successfully')
    } catch (err) {
      console.error('[Pyodide] Initialization error:', err)
      setError(err instanceof Error ? err.message : 'Failed to load Pyodide')
    } finally {
      setLoading(false)
    }
  }, [pyodide, loading])

  // Auto-load if enabled
  useEffect(() => {
    if (autoLoad && !pyodide && !loading) {
      loadPyodide()
    }
  }, [autoLoad, pyodide, loading, loadPyodide])

  // Run Python code
  const runPython = useCallback(
    async (code: string): Promise<ExecutionResult> => {
      if (!pyodide) {
        // Lazy load Pyodide if not loaded
        await loadPyodide()
        if (!pyodide) {
          return {
            success: false,
            output: null,
            stdout: '',
            stderr: 'Pyodide not loaded',
            executionTime: 0,
          }
        }
      }

      const startTime = performance.now()

      try {
        // Clear stdout/stderr
        pyodide.runPython(`
sys.stdout.clear()
sys.stderr.clear()
`)

        // Execute code
        const result = await pyodide.runPythonAsync(code)

        // Capture output
        const stdout = pyodide.runPython('sys.stdout.getvalue()') || ''
        const stderr = pyodide.runPython('sys.stderr.getvalue()') || ''

        const executionTime = performance.now() - startTime

        // Convert result to JS
        let jsResult = result
        if (result && typeof result.toJs === 'function') {
          jsResult = result.toJs()
        }

        return {
          success: true,
          output: jsResult,
          stdout,
          stderr,
          executionTime,
        }
      } catch (err) {
        const executionTime = performance.now() - startTime
        const stderr = pyodide.runPython('sys.stderr.getvalue()') || ''

        return {
          success: false,
          output: null,
          stdout: '',
          stderr: `${err}\n${stderr}`,
          executionTime,
        }
      }
    },
    [pyodide, loadPyodide]
  )

  // Install additional packages
  const installPackage = useCallback(
    async (packages: string | string[]) => {
      if (!pyodide) {
        throw new Error('Pyodide not loaded')
      }

      const packageList = Array.isArray(packages) ? packages : [packages]

      try {
        // Use micropip for pure Python packages
        await pyodide.runPythonAsync(`
import micropip
await micropip.install(${JSON.stringify(packageList)})
`)

        setLoadedPackages((prev) => [...new Set([...prev, ...packageList])])
        console.log('[Pyodide] Installed packages:', packageList)
      } catch (err) {
        console.error('[Pyodide] Package installation error:', err)
        throw err
      }
    },
    [pyodide]
  )

  const contextValue: PyodideContextType = {
    pyodide,
    loading,
    loadProgress,
    error,
    ready,
    runPython,
    installPackage,
    loadedPackages,
  }

  return <PyodideContext.Provider value={contextValue}>{children}</PyodideContext.Provider>
}

export function usePyodide(): PyodideContextType {
  const context = useContext(PyodideContext)
  if (!context) {
    throw new Error('usePyodide must be used within a PyodideProvider')
  }
  return context
}

export default PyodideContext
