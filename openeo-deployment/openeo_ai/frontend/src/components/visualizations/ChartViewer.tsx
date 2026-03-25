import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChartVisualization } from '@/types'
import { cn } from '@/lib/utils'

interface ChartViewerProps {
  data: ChartVisualization
  className?: string
}

const COLORS = [
  '#3B82F6', // blue
  '#10B981', // green
  '#F59E0B', // yellow
  '#EF4444', // red
  '#8B5CF6', // purple
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#F97316', // orange
]

export function ChartViewer({ data, className }: ChartViewerProps) {
  const chartData = data.xAxis.values.map((x, i) => {
    const point: Record<string, string | number> = { x: x.toString() }
    data.series.forEach((series) => {
      point[series.name] = series.values[i] ?? 0
    })
    return point
  })

  const handleDownload = () => {
    // Create CSV content
    const headers = ['x', ...data.series.map((s) => s.name)]
    const rows = chartData.map((point) =>
      [point.x, ...data.series.map((s) => point[s.name])].join(',')
    )
    const csv = [headers.join(','), ...rows].join('\n')

    // Download
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${data.title || 'chart'}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const renderChart = () => {
    const commonProps = {
      data: chartData,
      margin: { top: 10, right: 30, left: 0, bottom: 0 },
    }

    switch (data.chartType) {
      case 'area':
        return (
          <AreaChart {...commonProps}>
            <defs>
              {data.series.map((series, index) => (
                <linearGradient
                  key={series.name}
                  id={`gradient-${index}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="5%"
                    stopColor={series.color || COLORS[index % COLORS.length]}
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor={series.color || COLORS[index % COLORS.length]}
                    stopOpacity={0}
                  />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="x"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={data.yAxis.range || ['auto', 'auto']}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.5rem',
              }}
            />
            <Legend />
            {data.series.map((series, index) => (
              <Area
                key={series.name}
                type="monotone"
                dataKey={series.name}
                stroke={series.color || COLORS[index % COLORS.length]}
                fillOpacity={1}
                fill={`url(#gradient-${index})`}
              />
            ))}
          </AreaChart>
        )

      case 'bar':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="x" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={data.yAxis.range || ['auto', 'auto']}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.5rem',
              }}
            />
            <Legend />
            {data.series.map((series, index) => (
              <Bar
                key={series.name}
                dataKey={series.name}
                fill={series.color || COLORS[index % COLORS.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        )

      case 'line':
      default:
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="x" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={data.yAxis.range || ['auto', 'auto']}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '0.5rem',
              }}
            />
            <Legend />
            {data.series.map((series, index) => (
              <Line
                key={series.name}
                type="monotone"
                dataKey={series.name}
                stroke={series.color || COLORS[index % COLORS.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        )
    }
  }

  return (
    <div className={cn("flex flex-col", className)}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium">{data.title}</h3>
        <Button variant="ghost" size="icon" onClick={handleDownload} className="h-8 w-8">
          <Download className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>

      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>{data.xAxis.label}</span>
        <span>{data.yAxis.label}</span>
      </div>
    </div>
  )
}
