import React, { useState, useMemo } from 'react'
import { Map, BarChart2, Table2, GitBranch, Layers } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Visualization, ChartVisualization, MapVisualization, ProcessGraphVisualization, ProcessNode, BBox } from '@/types'
import { MapViewer } from './MapViewer'
import { ChartViewer } from './ChartViewer'
import { cn } from '@/lib/utils'

interface VisualizationPanelProps {
  visualizations: Visualization[]
  className?: string
  onBboxChange?: (bbox: BBox | null) => void
  bbox?: BBox | null
}

export function VisualizationPanel({ visualizations, className, onBboxChange, bbox }: VisualizationPanelProps) {
  const [activeTab, setActiveTab] = useState('map')

  const maps = visualizations.filter((v) => v.type === 'map' || v.type === 'comparison')
  const charts = visualizations.filter((v) => v.type === 'chart')
  const tables = visualizations.filter((v) => v.type === 'table')
  const processGraphs = visualizations.filter((v) => v.type === 'process_graph')

  const latestMap = maps[maps.length - 1]
  const latestChart = charts[charts.length - 1]
  const latestProcessGraph = processGraphs[processGraphs.length - 1]

  // Auto-switch to map tab when a new map visualization arrives
  const prevMapCount = React.useRef(maps.length)
  React.useEffect(() => {
    if (maps.length > prevMapCount.current) {
      setActiveTab('map')
    }
    prevMapCount.current = maps.length
  }, [maps.length])

  const hasAnyData = visualizations.length > 0

  return (
    <Card className={cn("flex h-full flex-col", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Results</CardTitle>
          <div className="flex gap-1">
            <Badge variant="success">High Quality</Badge>
            <Badge variant="default">Deep Analysis</Badge>
            <Badge variant="secondary">GeoTIFF + JSON</Badge>
          </div>
        </div>
      </CardHeader>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-1 flex-col overflow-hidden">
        <TabsList className="mx-4 grid w-auto grid-cols-5 gap-1">
          <TabsTrigger value="visualization" className="flex items-center gap-1 text-xs">
            <Layers className="h-3 w-3" />
            Visualization
          </TabsTrigger>
          <TabsTrigger value="map" className="flex items-center gap-1 text-xs">
            <Map className="h-3 w-3" />
            Map View
          </TabsTrigger>
          <TabsTrigger value="table" className="flex items-center gap-1 text-xs">
            <Table2 className="h-3 w-3" />
            Data Table
          </TabsTrigger>
          <TabsTrigger value="statistics" className="flex items-center gap-1 text-xs">
            <BarChart2 className="h-3 w-3" />
            Statistics
          </TabsTrigger>
          <TabsTrigger value="process" className="flex items-center gap-1 text-xs">
            <GitBranch className="h-3 w-3" />
            Process Graph
          </TabsTrigger>
        </TabsList>

        <CardContent className="flex flex-1 flex-col overflow-hidden p-4">
          <TabsContent value="visualization" className="mt-0 flex-1 overflow-hidden">
            {latestChart ? (
              <ChartViewer
                data={latestChart.data as ChartVisualization}
                className="h-full"
              />
            ) : hasAnyData ? (
              <EmptyState message="No visualization available yet" />
            ) : (
              <LoadingSkeleton type="chart" />
            )}
          </TabsContent>

          <TabsContent value="map" className="mt-0 flex-1 overflow-hidden">
            <MapViewer
              data={latestMap?.data as MapVisualization | undefined}
              title={latestMap?.title}
              className="h-full w-full"
              onBboxChange={onBboxChange}
              bbox={bbox}
            />
          </TabsContent>

          <TabsContent value="table" className="mt-0 flex-1 overflow-auto">
            {tables.length > 0 ? (
              <DataTable visualization={tables[tables.length - 1]} />
            ) : hasAnyData ? (
              <EmptyState message="No table data available yet" />
            ) : (
              <LoadingSkeleton type="table" />
            )}
          </TabsContent>

          <TabsContent value="statistics" className="mt-0 flex-1 overflow-auto">
            {latestChart ? (
              <StatisticsPanel data={latestChart.data as ChartVisualization} />
            ) : hasAnyData ? (
              <EmptyState message="No statistics available yet" />
            ) : (
              <LoadingSkeleton type="stats" />
            )}
          </TabsContent>

          <TabsContent value="process" className="mt-0 flex-1 overflow-auto">
            {latestProcessGraph ? (
              <ProcessGraphViewer
                data={latestProcessGraph.data as ProcessGraphVisualization}
              />
            ) : hasAnyData ? (
              <EmptyState message="No process graph available yet" />
            ) : (
              <LoadingSkeleton type="graph" />
            )}
          </TabsContent>
        </CardContent>
      </Tabs>
    </Card>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{message}</p>
    </div>
  )
}

// Skeleton loading placeholders
function SkeletonBlock({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div className={cn("animate-pulse rounded bg-muted", className)} style={style} />
  )
}

function LoadingSkeleton({ type }: { type: 'map' | 'chart' | 'table' | 'stats' | 'graph' }) {
  if (type === 'map') {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <SkeletonBlock className="h-6 w-48" />
        <SkeletonBlock className="flex-1 rounded-lg" />
        <div className="flex gap-2">
          <SkeletonBlock className="h-8 w-24" />
          <SkeletonBlock className="h-8 w-24" />
          <SkeletonBlock className="h-8 w-24" />
        </div>
      </div>
    )
  }

  if (type === 'chart') {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <SkeletonBlock className="h-6 w-40" />
        <div className="flex flex-1 items-end gap-2 pb-8">
          {[40, 65, 50, 80, 55, 70, 45, 60, 75, 50].map((h, i) => (
            <SkeletonBlock key={i} className="flex-1" style={{ height: `${h}%` }} />
          ))}
        </div>
        <SkeletonBlock className="h-4 w-full" />
      </div>
    )
  }

  if (type === 'table') {
    return (
      <div className="flex flex-col gap-2 p-4">
        <div className="flex gap-4">
          <SkeletonBlock className="h-8 flex-1" />
          <SkeletonBlock className="h-8 flex-1" />
          <SkeletonBlock className="h-8 flex-1" />
          <SkeletonBlock className="h-8 flex-1" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <SkeletonBlock className="h-6 flex-1" />
            <SkeletonBlock className="h-6 flex-1" />
            <SkeletonBlock className="h-6 flex-1" />
            <SkeletonBlock className="h-6 flex-1" />
          </div>
        ))}
      </div>
    )
  }

  if (type === 'stats') {
    return (
      <div className="grid gap-4 p-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4">
            <SkeletonBlock className="mb-3 h-5 w-32" />
            <div className="grid grid-cols-2 gap-2">
              <SkeletonBlock className="h-4 w-20" />
              <SkeletonBlock className="h-4 w-20" />
              <SkeletonBlock className="h-4 w-20" />
              <SkeletonBlock className="h-4 w-20" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  // graph
  return (
    <div className="flex flex-col items-center gap-4 p-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <React.Fragment key={i}>
          <SkeletonBlock className="h-16 w-64 rounded-lg" />
          {i < 2 && <SkeletonBlock className="h-8 w-0.5" />}
        </React.Fragment>
      ))}
    </div>
  )
}

function DataTable({ visualization }: { visualization: Visualization }) {
  const data = visualization.data as { headers: string[]; rows: (string | number)[][] }

  return (
    <div className="h-full overflow-auto rounded-md border">
      <table className="w-full">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {data.headers.map((header, i) => (
              <th key={i} className="px-4 py-2 text-left text-sm font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i} className="border-t hover:bg-muted/50">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 text-sm">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StatisticsPanel({ data }: { data: ChartVisualization }) {
  const stats = data.series.map((series) => {
    const values = series.values.filter((v) => !isNaN(v))
    const min = Math.min(...values)
    const max = Math.max(...values)
    const mean = values.reduce((a, b) => a + b, 0) / values.length
    const sortedValues = [...values].sort((a, b) => a - b)
    const median = sortedValues[Math.floor(sortedValues.length / 2)]

    return {
      name: series.name,
      min: min.toFixed(4),
      max: max.toFixed(4),
      mean: mean.toFixed(4),
      median: median.toFixed(4),
      count: values.length,
    }
  })

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">{data.title} - Statistics</h3>

      <div className="grid gap-4 md:grid-cols-2">
        {stats.map((s) => (
          <Card key={s.name}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{s.name}</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Min:</span> {s.min}
              </div>
              <div>
                <span className="text-muted-foreground">Max:</span> {s.max}
              </div>
              <div>
                <span className="text-muted-foreground">Mean:</span> {s.mean}
              </div>
              <div>
                <span className="text-muted-foreground">Median:</span> {s.median}
              </div>
              <div className="col-span-2">
                <span className="text-muted-foreground">Count:</span> {s.count}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

// Resolve from_node references to build edges automatically
function resolveEdges(nodes: ProcessNode[]): { source: string; target: string; argument: string }[] {
  const edges: { source: string; target: string; argument: string }[] = []
  for (const node of nodes) {
    for (const [argKey, argValue] of Object.entries(node.arguments)) {
      if (
        argValue &&
        typeof argValue === 'object' &&
        'from_node' in (argValue as Record<string, unknown>)
      ) {
        const fromNode = (argValue as { from_node: string }).from_node
        edges.push({ source: fromNode, target: node.id, argument: argKey })
      }
    }
  }
  return edges
}

// Compute topological ordering for vertical layout
function topoSort(nodes: ProcessNode[], edges: { source: string; target: string }[]): string[] {
  const inDegree: Record<string, number> = {}
  const adj: Record<string, string[]> = {}
  for (const node of nodes) {
    inDegree[node.id] = 0
    adj[node.id] = []
  }
  for (const edge of edges) {
    if (adj[edge.source]) adj[edge.source].push(edge.target)
    inDegree[edge.target] = (inDegree[edge.target] || 0) + 1
  }
  const queue: string[] = []
  for (const id of Object.keys(inDegree)) {
    if (inDegree[id] === 0) queue.push(id)
  }
  const sorted: string[] = []
  while (queue.length > 0) {
    const current = queue.shift()!
    sorted.push(current)
    for (const neighbor of adj[current] || []) {
      inDegree[neighbor] = (inDegree[neighbor] || 0) - 1
      if (inDegree[neighbor] === 0) queue.push(neighbor)
    }
  }
  // Add any remaining nodes (cycles or disconnected)
  for (const node of nodes) {
    if (!sorted.includes(node.id)) sorted.push(node.id)
  }
  return sorted
}

function ProcessGraphViewer({ data }: { data: ProcessGraphVisualization }) {
  // Derive edges from from_node references if explicit edges are empty
  const edges = useMemo(() => {
    if (data.edges.length > 0) return data.edges
    return resolveEdges(data.nodes)
  }, [data.nodes, data.edges])

  const sortedIds = useMemo(() => topoSort(data.nodes, edges), [data.nodes, edges])

  const nodeMap = useMemo(() => {
    const map: Record<string, ProcessNode> = {}
    for (const node of data.nodes) map[node.id] = node
    return map
  }, [data.nodes])

  // Layout constants
  const NODE_WIDTH = 280
  const NODE_HEIGHT = 80
  const VERTICAL_GAP = 48
  const LEFT_PADDING = 40
  const TOP_PADDING = 24

  // Compute positions for each node
  const positions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {}
    sortedIds.forEach((id, i) => {
      pos[id] = {
        x: LEFT_PADDING,
        y: TOP_PADDING + i * (NODE_HEIGHT + VERTICAL_GAP),
      }
    })
    return pos
  }, [sortedIds])

  const totalHeight = TOP_PADDING + sortedIds.length * (NODE_HEIGHT + VERTICAL_GAP)
  const totalWidth = LEFT_PADDING * 2 + NODE_WIDTH

  return (
    <div className="h-full overflow-auto rounded-md border bg-foreground/5 p-4">
      <h3 className="mb-4 text-lg font-medium">Process Graph</h3>

      <div className="relative" style={{ minHeight: totalHeight, minWidth: totalWidth }}>
        {/* SVG arrows layer */}
        <svg
          className="pointer-events-none absolute left-0 top-0"
          width={totalWidth}
          height={totalHeight}
          style={{ zIndex: 0 }}
        >
          <defs>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="6"
              refX="8"
              refY="3"
              orient="auto"
            >
              <polygon
                points="0 0, 8 3, 0 6"
                className="fill-muted-foreground"
              />
            </marker>
          </defs>
          {edges.map((edge, i) => {
            const srcPos = positions[edge.source]
            const tgtPos = positions[edge.target]
            if (!srcPos || !tgtPos) return null

            const x1 = srcPos.x + NODE_WIDTH / 2
            const y1 = srcPos.y + NODE_HEIGHT
            const x2 = tgtPos.x + NODE_WIDTH / 2
            const y2 = tgtPos.y

            // Bezier curve for nicer lines
            const midY = (y1 + y2) / 2

            return (
              <g key={i}>
                <path
                  d={`M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`}
                  className="process-edge"
                  markerEnd="url(#arrowhead)"
                />
                {/* Edge label */}
                <text
                  x={(x1 + x2) / 2 + 8}
                  y={midY}
                  className="fill-muted-foreground text-[10px]"
                  dominantBaseline="middle"
                >
                  {edge.argument}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Node cards layer */}
        {sortedIds.map((id) => {
          const node = nodeMap[id]
          if (!node) return null
          const pos = positions[id]
          if (!pos) return null

          // Check if this node has a from_node dependency to highlight
          const incomingEdges = edges.filter((e) => e.target === id)

          return (
            <div
              key={id}
              className="absolute rounded-lg border bg-card shadow-sm transition-shadow hover:shadow-md"
              style={{
                left: pos.x,
                top: pos.y,
                width: NODE_WIDTH,
                height: NODE_HEIGHT,
                zIndex: 1,
              }}
            >
              <div className="flex h-full items-start gap-2 p-3">
                <div className="shrink-0 rounded bg-primary/10 px-2 py-1 text-xs font-mono text-primary">
                  {id}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-sm">{node.process_id}</div>
                  <div className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
                    {Object.entries(node.arguments)
                      .filter(([, value]) => {
                        // Skip from_node refs in display (shown as arrows)
                        if (value && typeof value === 'object' && 'from_node' in (value as Record<string, unknown>)) return false
                        return true
                      })
                      .slice(0, 2)
                      .map(([key, value]) => (
                        <div key={key} className="truncate">
                          <span className="font-mono">{key}:</span>{' '}
                          {typeof value === 'object'
                            ? JSON.stringify(value).slice(0, 30) + '...'
                            : String(value)}
                        </div>
                      ))}
                    {incomingEdges.length > 0 && (
                      <div className="text-primary/70">
                        {incomingEdges.map((e) => e.source).join(', ')} {'->'} here
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
