import type { ResultTypeConfig } from '@/hooks/useResultType'

// CSS gradients for common colormaps
const COLORMAP_GRADIENTS: Record<string, string> = {
  viridis: 'linear-gradient(to right, #440154, #482777, #3e4989, #31688e, #26838f, #1f9d8a, #6cce5a, #b6de2b, #fee825)',
  rdylgn: 'linear-gradient(to right, #a50026, #d73027, #f46d43, #fdae61, #fee08b, #ffffbf, #d9ef8b, #a6d96a, #66bd63, #1a9850, #006837)',
  terrain: 'linear-gradient(to right, #333399, #0099cc, #00cc66, #99cc00, #cccc00, #cc9900, #cc6633, #993333, #ffffff)',
  plasma: 'linear-gradient(to right, #0d0887, #5b02a3, #9a179b, #cb4679, #eb7852, #fbb32f, #f0f921)',
  inferno: 'linear-gradient(to right, #000004, #1b0c41, #4a0c6b, #781c6d, #a52c60, #cf4446, #ed6925, #fb9b06, #f7d13d, #fcffa4)',
  magma: 'linear-gradient(to right, #000004, #180f3d, #440f76, #721f81, #9e2f7f, #cd4071, #f1605d, #fd9668, #feca8d, #fcfdbf)',
  coolwarm: 'linear-gradient(to right, #3b4cc0, #6788ee, #9abbff, #c9d7ef, #edd1c2, #f7a889, #e26952, #b40426)',
  rdbu: 'linear-gradient(to right, #67001f, #b2182b, #d6604d, #f4a582, #fddbc7, #f7f7f7, #d1e5f0, #92c5de, #4393c3, #2166ac, #053061)',
  ylgnbu: 'linear-gradient(to right, #ffffd9, #edf8b1, #c7e9b4, #7fcdbb, #41b6c4, #1d91c0, #225ea8, #253494, #081d58)',
  spectral: 'linear-gradient(to right, #9e0142, #d53e4f, #f46d43, #fdae61, #fee08b, #ffffbf, #e6f598, #abdda4, #66c2a5, #3288bd, #5e4fa2)',
}

function getGradient(colormap: string): string {
  const key = colormap.toLowerCase().replace(/[_-]/g, '')
  return COLORMAP_GRADIENTS[key] ?? COLORMAP_GRADIENTS.viridis
}

interface ColorLegendProps {
  vmin: number
  vmax: number
  colormap: string
  resultConfig: ResultTypeConfig
}

export function ColorLegend({ vmin, vmax, colormap, resultConfig }: ColorLegendProps) {
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-white/20 bg-black/70 px-2.5 py-1.5 backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[10px] font-medium text-white/90">{resultConfig.label}</span>
        {resultConfig.unit && (
          <span className="text-[9px] text-white/60">({resultConfig.unit})</span>
        )}
      </div>
      <div
        className="h-3 w-44 rounded-sm"
        style={{ background: getGradient(colormap) }}
      />
      <div className="flex justify-between">
        <span className="text-[9px] tabular-nums text-white/80">
          {resultConfig.formatValue(vmin)}
        </span>
        <span className="text-[9px] tabular-nums text-white/80">
          {resultConfig.formatValue(vmax)}
        </span>
      </div>
      {resultConfig.legendLabels && (
        <div className="flex justify-between">
          <span className="text-[8px] text-white/50">{resultConfig.legendLabels.low}</span>
          <span className="text-[8px] text-white/50">{resultConfig.legendLabels.high}</span>
        </div>
      )}
    </div>
  )
}
