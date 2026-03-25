import React from 'react'
import { Leaf, Cpu, HardDrive, Zap } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SustainabilityMetrics } from '@/types'
import { cn, formatBytes } from '@/lib/utils'

interface SustainabilityPanelProps {
  metrics: SustainabilityMetrics | null
  className?: string
}

export function SustainabilityPanel({ metrics, className }: SustainabilityPanelProps) {
  // Default metrics if none provided
  const displayMetrics = metrics || {
    carbonFootprint: 0,
    dataTransferred: 0,
    computeTime: 0,
    energyUsed: 0,
  }

  const getCarbonImpact = (kg: number): { label: string; color: string } => {
    if (kg < 0.01) return { label: 'Minimal', color: 'text-emerald-500' }
    if (kg < 0.1) return { label: 'Low', color: 'text-blue-500' }
    if (kg < 1) return { label: 'Moderate', color: 'text-yellow-500' }
    return { label: 'High', color: 'text-red-500' }
  }

  const impact = getCarbonImpact(displayMetrics.carbonFootprint)

  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Leaf className="h-4 w-4 text-emerald-500" />
          Sustainability
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Carbon Footprint */}
        <div className="rounded-lg bg-muted/50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Carbon Footprint</span>
            <span className={cn("text-lg font-semibold", impact.color)}>
              {displayMetrics.carbonFootprint.toFixed(3)} kg
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">CO₂ equivalent</span>
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", impact.color, "bg-current/10")}>
              {impact.label}
            </span>
          </div>
        </div>

        {/* Other Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard
            icon={<HardDrive className="h-4 w-4" />}
            label="Data Transferred"
            value={formatBytes(displayMetrics.dataTransferred)}
          />
          <MetricCard
            icon={<Cpu className="h-4 w-4" />}
            label="Compute Time"
            value={formatTime(displayMetrics.computeTime)}
          />
          <MetricCard
            icon={<Zap className="h-4 w-4" />}
            label="Energy Used"
            value={`${displayMetrics.energyUsed.toFixed(4)} kWh`}
          />
          <MetricCard
            icon={<Leaf className="h-4 w-4" />}
            label="Trees to Offset"
            value={`${Math.ceil(displayMetrics.carbonFootprint * 0.5)}`}
          />
        </div>

        {/* Tips */}
        <div className="border-t pt-3">
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
            Tips for Reducing Impact
          </h4>
          <ul className="space-y-1 text-xs text-muted-foreground">
            <li>• Use smaller spatial extents when possible</li>
            <li>• Limit temporal ranges to what's needed</li>
            <li>• Request only necessary bands</li>
            <li>• Use cloud-free imagery filters</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg border bg-card p-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  )
}

function formatTime(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  return `${minutes}m ${remainingSeconds}s`
}
