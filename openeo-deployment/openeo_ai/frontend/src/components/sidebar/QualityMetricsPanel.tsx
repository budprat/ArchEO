import React from 'react'
import { AlertCircle, CheckCircle2, Info, Cloud, Calendar, MapPin, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

// Backend sends metrics in this format
interface BackendQualityMetrics {
  cloud_coverage?: {
    estimated_cloud_cover_pct?: number
    confidence?: string
  }
  temporal_coverage?: {
    coverage_pct?: number
    requested_days?: number
    available_days?: number
  }
  overall_quality?: {
    grade?: string
    score?: number
  }
  recommendations?: string[]
  // Also support the frontend format
  overallScore?: number
  grade?: string
  cloudCoverage?: number
  temporalCoverage?: number
  spatialCoverage?: number
  validPixelPercentage?: number
}

interface QualityMetricsPanelProps {
  metrics: BackendQualityMetrics | null
  className?: string
}

function ColoredProgress({ value, className }: { value: number; className?: string }) {
  const safeValue = typeof value === 'number' && !isNaN(value) ? value : 0
  const getBarColor = () => {
    if (safeValue >= 80) return 'bg-success'
    if (safeValue >= 60) return 'bg-primary'
    if (safeValue >= 40) return 'bg-yellow-500'
    return 'bg-destructive'
  }

  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500 ease-out", getBarColor())}
        style={{ width: `${Math.min(100, Math.max(0, safeValue))}%` }}
      />
    </div>
  )
}

function getQualityGrade(score: number): { grade: string; color: string } {
  if (score >= 90) return { grade: 'A', color: 'quality-a' }
  if (score >= 80) return { grade: 'B', color: 'quality-b' }
  if (score >= 70) return { grade: 'C', color: 'quality-c' }
  if (score >= 60) return { grade: 'D', color: 'quality-d' }
  return { grade: 'F', color: 'quality-f' }
}

// Helper to safely extract numeric value
function safeNumber(value: unknown, defaultValue = 0): number {
  if (typeof value === 'number' && !isNaN(value)) return value
  if (typeof value === 'string') {
    const parsed = parseFloat(value)
    if (!isNaN(parsed)) return parsed
  }
  return defaultValue
}

export function QualityMetricsPanel({ metrics, className }: QualityMetricsPanelProps) {
  if (!metrics) {
    return (
      <Card className={cn("border-0 shadow-none", className)}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Activity className="h-4 w-4 text-muted-foreground" />
            Quality Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center py-8 text-center">
            <div className="mb-3 rounded-xl bg-muted/50 p-3">
              <Activity className="h-6 w-6 text-muted-foreground/50" />
            </div>
            <p className="text-sm text-muted-foreground">
              Metrics appear after analysis
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Extract values from either backend or frontend format
  const cloudCoverage = safeNumber(
    metrics.cloudCoverage ?? metrics.cloud_coverage?.estimated_cloud_cover_pct
  )
  const temporalCoverage = safeNumber(
    metrics.temporalCoverage ?? metrics.temporal_coverage?.coverage_pct,
    100
  )
  const overallScore = safeNumber(
    metrics.overallScore ?? metrics.overall_quality?.score,
    70
  )
  const grade = metrics.grade ?? metrics.overall_quality?.grade ?? getQualityGrade(overallScore).grade
  const recommendations = metrics.recommendations ?? []

  const { color } = getQualityGrade(overallScore)

  return (
    <Card className={cn("border-0 shadow-none", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 font-semibold">
            <Activity className="h-4 w-4 text-muted-foreground" />
            Quality Metrics
          </span>
          <Badge className={cn("text-sm font-bold px-3 py-0.5", color)}>{grade}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Overall Score */}
        <div>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-medium">Overall Score</span>
            <span className="font-semibold tabular-nums">{overallScore.toFixed(0)}%</span>
          </div>
          <ColoredProgress value={overallScore} className="h-2" />
        </div>

        {/* Individual Metrics */}
        <div className="space-y-4">
          <MetricItem
            icon={<Cloud className="h-4 w-4" />}
            label="Cloud Coverage"
            value={cloudCoverage}
            inverse
          />
          <MetricItem
            icon={<Calendar className="h-4 w-4" />}
            label="Temporal Coverage"
            value={temporalCoverage}
          />
          <MetricItem
            icon={<MapPin className="h-4 w-4" />}
            label="Spatial Coverage"
            value={safeNumber(metrics.spatialCoverage, 100)}
          />
          <MetricItem
            icon={<CheckCircle2 className="h-4 w-4" />}
            label="Valid Pixels"
            value={safeNumber(metrics.validPixelPercentage, 100 - cloudCoverage)}
          />
        </div>

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div className="border-t pt-4">
            <h4 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Info className="h-3 w-3" />
              Recommendations
            </h4>
            <ul className="space-y-2">
              {recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2 text-xs leading-relaxed">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-500" />
                  <span className="text-muted-foreground">{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function MetricItem({
  icon,
  label,
  value,
  inverse = false,
}: {
  icon: React.ReactNode
  label: string
  value: number
  inverse?: boolean
}) {
  const safeValue = safeNumber(value)
  const progressValue = inverse ? 100 - safeValue : safeValue

  const getColor = () => {
    if (progressValue >= 80) return 'text-success'
    if (progressValue >= 60) return 'text-primary'
    if (progressValue >= 40) return 'text-yellow-500'
    return 'text-destructive'
  }

  return (
    <div className="flex items-center gap-3">
      <div className="text-muted-foreground/60">{icon}</div>
      <div className="flex-1">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-muted-foreground">{label}</span>
          <span className={cn("font-semibold tabular-nums", getColor())}>{safeValue.toFixed(1)}%</span>
        </div>
        <ColoredProgress value={progressValue} className="mt-1.5" />
      </div>
    </div>
  )
}
