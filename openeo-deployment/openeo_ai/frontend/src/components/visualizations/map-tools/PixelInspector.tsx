import { useEffect, useRef } from 'react'
import { useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import type { ResultTypeConfig } from '@/hooks/useResultType'

interface PixelInspectorProps {
  active: boolean
  bounds?: [[number, number], [number, number]]
  vmin?: number
  vmax?: number
  resultConfig: ResultTypeConfig
}

export function PixelInspector({ active, bounds, vmin, vmax, resultConfig }: PixelInspectorProps) {
  const map = useMap()
  const popupRef = useRef<L.Popup | null>(null)

  // Change cursor when inspector is active
  useEffect(() => {
    const container = map.getContainer()
    if (active) {
      container.style.cursor = 'crosshair'
    } else {
      container.style.cursor = ''
      if (popupRef.current) {
        map.closePopup(popupRef.current)
        popupRef.current = null
      }
    }
    return () => {
      container.style.cursor = ''
    }
  }, [active, map])

  useMapEvents({
    click(e) {
      if (!active || !bounds || vmin === undefined || vmax === undefined) return

      const { lat, lng } = e.latlng
      const [[south, west], [north, east]] = bounds

      // Check if click is within raster bounds
      if (lat < south || lat > north || lng < west || lng > east) return

      // Estimate value based on position within bounds (rough approximation)
      // For a more accurate readback we'd need the actual raster data or canvas pixel sampling
      // This uses the canvas pixel approach: find the ImageOverlay's canvas/image and sample it
      const value = samplePixelValue(map, e.containerPoint, vmin, vmax)

      const content = `
        <div style="font-family: system-ui; font-size: 12px; line-height: 1.5; min-width: 140px;">
          <div style="font-weight: 600; margin-bottom: 4px; border-bottom: 1px solid #e5e5e5; padding-bottom: 3px;">
            ${resultConfig.label}
          </div>
          <div><span style="color: #888;">Lat:</span> ${lat.toFixed(5)}</div>
          <div><span style="color: #888;">Lng:</span> ${lng.toFixed(5)}</div>
          ${value !== null ? `
            <div style="margin-top: 4px; padding-top: 3px; border-top: 1px solid #e5e5e5;">
              <span style="color: #888;">Value:</span> <strong>${resultConfig.formatValue(value)}</strong>
            </div>
            ${getInterpretation(value, resultConfig) ? `
              <div style="color: #666; font-size: 11px;">${getInterpretation(value, resultConfig)}</div>
            ` : ''}
          ` : `
            <div style="margin-top: 4px; color: #999; font-size: 11px;">Click on the raster overlay</div>
          `}
        </div>
      `

      if (popupRef.current) {
        map.closePopup(popupRef.current)
      }

      popupRef.current = L.popup({ closeButton: true, className: 'pixel-inspector-popup' })
        .setLatLng(e.latlng)
        .setContent(content)
        .openOn(map)
    },
  })

  return null
}

function samplePixelValue(
  map: L.Map,
  containerPoint: L.Point,
  vmin: number,
  vmax: number
): number | null {
  try {
    // Find the image overlay element in the map pane
    const panes = map.getContainer()
    const images = panes.querySelectorAll<HTMLImageElement>('.leaflet-image-layer')
    if (images.length === 0) return null

    const img = images[images.length - 1] // Latest overlay

    // Create offscreen canvas to sample the pixel
    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth || img.width
    canvas.height = img.naturalHeight || img.height
    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    // Convert container point to image pixel coordinates
    const imgRect = img.getBoundingClientRect()
    const mapRect = map.getContainer().getBoundingClientRect()

    const relX = (containerPoint.x + mapRect.left - imgRect.left) / imgRect.width
    const relY = (containerPoint.y + mapRect.top - imgRect.top) / imgRect.height

    if (relX < 0 || relX > 1 || relY < 0 || relY > 1) return null

    const px = Math.floor(relX * canvas.width)
    const py = Math.floor(relY * canvas.height)

    const pixel = ctx.getImageData(px, py, 1, 1).data
    const [r, g, b, a] = pixel

    // Skip transparent pixels
    if (a < 10) return null

    // Convert grayscale intensity to value (simple linear mapping)
    // For colormapped images, luminance is a rough proxy
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return vmin + luminance * (vmax - vmin)
  } catch {
    return null
  }
}

function getInterpretation(value: number, config: ResultTypeConfig): string | null {
  if (config.type === 'ndvi') {
    if (value < -0.1) return 'Water'
    if (value < 0.1) return 'Bare soil / rock'
    if (value < 0.2) return 'Sparse vegetation'
    if (value < 0.4) return 'Light vegetation'
    if (value < 0.6) return 'Moderate vegetation'
    return 'Dense vegetation'
  }
  if (config.type === 'ndwi') {
    if (value < -0.3) return 'Dry land'
    if (value < 0) return 'Low moisture'
    if (value < 0.3) return 'Moderate water'
    return 'Water body'
  }
  return null
}
