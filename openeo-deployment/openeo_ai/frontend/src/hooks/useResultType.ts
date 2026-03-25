import type { MapVisualization } from '@/types'

export type AnalysisType = 'ndvi' | 'ndwi' | 'terrain' | 'change_detection' | 'segmentation' | 'generic'

export interface ResultTypeConfig {
  type: AnalysisType
  label: string
  unit: string
  formatValue: (v: number) => string
  legendLabels?: { low: string; high: string }
}

function safe(v: number, fn: (n: number) => string): string {
  if (v == null || Number.isNaN(v)) return '—'
  return fn(v)
}

const CONFIGS: Record<AnalysisType, Omit<ResultTypeConfig, 'type'>> = {
  ndvi: {
    label: 'NDVI',
    unit: '',
    formatValue: (v) => safe(v, n => n.toFixed(3)),
    legendLabels: { low: 'Bare soil / Water', high: 'Dense vegetation' },
  },
  ndwi: {
    label: 'NDWI',
    unit: '',
    formatValue: (v) => safe(v, n => n.toFixed(3)),
    legendLabels: { low: 'Dry land', high: 'Water' },
  },
  terrain: {
    label: 'Elevation',
    unit: 'm',
    formatValue: (v) => safe(v, n => `${Math.round(n)} m`),
    legendLabels: { low: 'Low', high: 'High' },
  },
  change_detection: {
    label: 'Change',
    unit: '',
    formatValue: (v) => safe(v, n => n.toFixed(3)),
    legendLabels: { low: 'Decrease', high: 'Increase' },
  },
  segmentation: {
    label: 'Class',
    unit: '',
    formatValue: (v) => safe(v, n => `Class ${Math.round(n)}`),
  },
  generic: {
    label: 'Value',
    unit: '',
    formatValue: (v) => safe(v, n => n.toFixed(4)),
  },
}

export function detectResultType(data?: MapVisualization, title?: string): ResultTypeConfig {
  const t = (title ?? '').toLowerCase()
  const cmap = (data?.colormap ?? '').toLowerCase()

  let type: AnalysisType = 'generic'

  if (/\bndvi\b|vegetation\sindex|\bevi\b/.test(t) || (cmap === 'rdylgn' && data?.vmin !== undefined && data.vmin < 0)) {
    type = 'ndvi'
  } else if (/\bndwi\b|water\sindex/.test(t)) {
    type = 'ndwi'
  } else if (/\bdem\b|\belevation\b|\bterrain\b|\bheight\b|\baltitude\b/.test(t) || cmap === 'terrain') {
    type = 'terrain'
  } else if (/\bchange\b|\bdifference\b|\bcompare\b/.test(t)) {
    type = 'change_detection'
  } else if (/\bsegment|\bclassif|\bland\s?cover|\bcanopy\b/.test(t)) {
    type = 'segmentation'
  }

  return { type, ...CONFIGS[type] }
}
