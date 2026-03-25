// Thinking step for displaying AI processing
export interface ThinkingStep {
  id: string
  type: 'analyzing' | 'planning' | 'executing' | 'processing' | 'fetching' | 'validating'
  message: string
  timestamp: Date
  completed?: boolean
}

// Message types
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
  visualizations?: Visualization[]
  thinkingSteps?: ThinkingStep[]
  isStreaming?: boolean
  toolName?: string
  toolResult?: unknown
}

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  result?: unknown
  status: 'pending' | 'running' | 'completed' | 'error'
}

// Visualization types
export type VisualizationType = 'map' | 'chart' | 'comparison' | 'table' | 'process_graph'

export interface Visualization {
  id: string
  type: VisualizationType
  title?: string
  data: MapVisualization | ChartVisualization | ComparisonVisualization | TableVisualization | ProcessGraphVisualization
}

export interface MapVisualization {
  type: 'raster' | 'vector'
  url?: string
  bounds?: [[number, number], [number, number]]
  colormap?: string
  opacity?: number
  geojson?: GeoJSON.FeatureCollection
  vmin?: number
  vmax?: number
  source?: string
  colorbar?: { min: number; max: number; colormap: string }
}

export interface ChartVisualization {
  chartType: 'line' | 'bar' | 'area' | 'scatter'
  title: string
  xAxis: {
    label: string
    values: (string | number)[]
  }
  yAxis: {
    label: string
    range?: [number, number]
  }
  series: {
    name: string
    values: number[]
    color?: string
  }[]
}

export interface ComparisonVisualization {
  before: MapVisualization
  after: MapVisualization
  labels?: {
    before: string
    after: string
  }
}

export interface TableVisualization {
  headers: string[]
  rows: (string | number)[][]
}

export interface ProcessGraphVisualization {
  nodes: ProcessNode[]
  edges: ProcessEdge[]
}

export interface ProcessNode {
  id: string
  process_id: string
  arguments: Record<string, unknown>
  position?: { x: number; y: number }
}

export interface ProcessEdge {
  source: string
  target: string
  argument: string
}

// Quality metrics
export interface QualityMetrics {
  overallScore: number
  grade: string
  cloudCoverage: number
  temporalCoverage: number
  spatialCoverage: number
  validPixelPercentage: number
  recommendations: string[]
}

// Sustainability metrics
export interface SustainabilityMetrics {
  carbonFootprint: number // kg CO2
  dataTransferred: number // bytes
  computeTime: number // seconds
  energyUsed: number // kWh
}

// Workflow
export interface Workflow {
  id: string
  name: string
  description?: string
  status: 'idle' | 'running' | 'completed' | 'error'
  steps: WorkflowStep[]
  processGraph?: Record<string, unknown>
  createdAt: Date
  completedAt?: Date
}

export interface WorkflowStep {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'error'
  tool?: string
  arguments?: Record<string, unknown>
  result?: unknown
  startedAt?: Date
  completedAt?: Date
}

// WebSocket message types
export interface WSMessage {
  type: 'message' | 'tool_start' | 'tool_result' | 'visualization' | 'quality_metrics' | 'error' | 'status'
  data: unknown
}

// Collection types
export interface Collection {
  id: string
  title: string
  description?: string
  extent: {
    spatial: { bbox: number[][] }
    temporal: { interval: string[][] }
  }
  keywords?: string[]
}

// Process types
export interface Process {
  id: string
  summary: string
  description?: string
  parameters: ProcessParameter[]
  returns: ProcessReturn
}

export interface ProcessParameter {
  name: string
  description: string
  schema: Record<string, unknown>
  required?: boolean
  default?: unknown
}

export interface ProcessReturn {
  description: string
  schema: Record<string, unknown>
}

// Bounding box
export interface BBox {
  west: number
  south: number
  east: number
  north: number
}

// Saved job from persistent archive
export interface SavedJob {
  save_id: string
  title: string
  result_path: string
  bounds?: number[]
  colormap: string
  vmin?: number
  vmax?: number
  size_bytes: number
  created_at: string
}

// Project
export interface Project {
  id: string
  name: string
  description: string
  analysisCount: number
  createdAt: string
  updatedAt: string
}

// Clarification (AskUserQuestion)
export interface ClarificationOption {
  label: string
  description: string
}

export interface ClarificationQuestion {
  question: string
  header: string
  options: ClarificationOption[]
  multiSelect?: boolean
}

// Export types
export type ExportFormat = 'notebook' | 'json' | 'markdown' | 'bibtex'

export interface ExportOptions {
  format: ExportFormat
  includeVisualizations: boolean
  includeQualityMetrics: boolean
  includeProcessGraph: boolean
}
