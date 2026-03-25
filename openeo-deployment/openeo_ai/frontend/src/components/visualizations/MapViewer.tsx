import { useRef, useState, useEffect, useCallback } from 'react'
import { MapContainer, TileLayer, ImageOverlay, GeoJSON, useMap } from 'react-leaflet'
import { LatLngBoundsExpression } from 'leaflet'
import { Layers, ZoomIn, ZoomOut, Download, Square, X, Crosshair, MousePointer, Search } from 'lucide-react'
import L from 'leaflet'
import { MapVisualization, BBox } from '@/types'
import { cn } from '@/lib/utils'
import { detectResultType } from '@/hooks/useResultType'
import { ColorLegend } from './map-tools/ColorLegend'
import { OpacitySlider } from './map-tools/OpacitySlider'
import { PixelInspector } from './map-tools/PixelInspector'

interface MapViewerProps {
  data?: MapVisualization
  title?: string
  className?: string
  onBboxChange?: (bbox: BBox | null) => void
  bbox?: BBox | null
}

const BASEMAPS = {
  osm: {
    name: 'Streets',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
  satellite: {
    name: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri',
  },
  terrain: {
    name: 'Terrain',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap',
  },
}

const COLORMAPS = ['viridis', 'plasma', 'inferno', 'magma', 'cividis', 'RdYlGn', 'RdYlBu', 'Spectral']

// Component to fit map bounds when they change
function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap()
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [20, 20] })
    }
  }, [map, bounds])
  return null
}

// Bbox drawing logic — rendered inside MapContainer to use useMap()
function BboxDrawHandler({
  isDrawing,
  bbox,
  onBboxChange,
  onDrawEnd,
}: {
  isDrawing: boolean
  bbox: BBox | null
  onBboxChange: (bbox: BBox | null) => void
  onDrawEnd: () => void
}) {
  const map = useMap()
  const drawingRef = useRef(false)
  const startRef = useRef<L.LatLng | null>(null)
  const previewRef = useRef<L.Rectangle | null>(null)
  const bboxRectRef = useRef<L.Rectangle | null>(null)
  const onBboxChangeRef = useRef(onBboxChange)
  const onDrawEndRef = useRef(onDrawEnd)

  useEffect(() => { onBboxChangeRef.current = onBboxChange }, [onBboxChange])
  useEffect(() => { onDrawEndRef.current = onDrawEnd }, [onDrawEnd])

  // Sync bbox display
  useEffect(() => {
    if (bboxRectRef.current) {
      map.removeLayer(bboxRectRef.current)
      bboxRectRef.current = null
    }
    if (bbox) {
      bboxRectRef.current = L.rectangle(
        [[bbox.south, bbox.west], [bbox.north, bbox.east]],
        { color: '#3b82f6', weight: 2, opacity: 0.8, fillOpacity: 0.1, dashArray: '6 3' }
      ).addTo(map)
    }
    return () => {
      if (bboxRectRef.current) {
        map.removeLayer(bboxRectRef.current)
        bboxRectRef.current = null
      }
    }
  }, [bbox, map])

  // Drawing mode
  useEffect(() => {
    if (!isDrawing) return

    map.dragging.disable()
    map.getContainer().style.cursor = 'crosshair'

    const onMouseDown = (e: L.LeafletMouseEvent) => {
      drawingRef.current = true
      startRef.current = e.latlng
      if (previewRef.current) {
        map.removeLayer(previewRef.current)
        previewRef.current = null
      }
    }

    const onMouseMove = (e: L.LeafletMouseEvent) => {
      if (!drawingRef.current || !startRef.current) return
      const bounds = L.latLngBounds(startRef.current, e.latlng)
      if (previewRef.current) {
        previewRef.current.setBounds(bounds)
      } else {
        previewRef.current = L.rectangle(bounds, {
          color: '#3b82f6', weight: 2, opacity: 0.8, fillOpacity: 0.1, dashArray: '6 3',
        }).addTo(map)
      }
    }

    const onMouseUp = (e: L.LeafletMouseEvent) => {
      if (!drawingRef.current || !startRef.current) return
      drawingRef.current = false

      const bounds = L.latLngBounds(startRef.current, e.latlng)
      const size = map.latLngToContainerPoint(bounds.getNorthEast())
        .distanceTo(map.latLngToContainerPoint(bounds.getSouthWest()))

      if (previewRef.current) {
        map.removeLayer(previewRef.current)
        previewRef.current = null
      }

      if (size > 5) {
        const newBbox = {
          west: parseFloat(bounds.getWest().toFixed(6)),
          south: parseFloat(bounds.getSouth().toFixed(6)),
          east: parseFloat(bounds.getEast().toFixed(6)),
          north: parseFloat(bounds.getNorth().toFixed(6)),
        }
        onBboxChangeRef.current(newBbox)
        map.fitBounds(bounds, { padding: [30, 30], animate: true })
      }

      onDrawEndRef.current()
    }

    map.on('mousedown', onMouseDown)
    map.on('mousemove', onMouseMove)
    map.on('mouseup', onMouseUp)

    return () => {
      map.off('mousedown', onMouseDown)
      map.off('mousemove', onMouseMove)
      map.off('mouseup', onMouseUp)
      map.dragging.enable()
      map.getContainer().style.cursor = ''
      drawingRef.current = false
      startRef.current = null
      if (previewRef.current) {
        map.removeLayer(previewRef.current)
        previewRef.current = null
      }
    }
  }, [isDrawing, map])

  return null
}

// Convert bounds from various formats to Leaflet format
function convertBounds(b: unknown): LatLngBoundsExpression {
  const defaultBounds: LatLngBoundsExpression = [[-60, -180], [80, 180]]
  if (!b) return defaultBounds
  if (Array.isArray(b) && b.length === 2 && Array.isArray(b[0])) return b as LatLngBoundsExpression
  if (Array.isArray(b) && b.length === 4 && typeof b[0] === 'number') {
    const [west, south, east, north] = b as number[]
    return [[south, west], [north, east]]
  }
  if (typeof b === 'object' && b !== null && 'west' in b) {
    const bbox = b as { west: number; south: number; east: number; north: number }
    return [[bbox.south, bbox.west], [bbox.north, bbox.east]]
  }
  return defaultBounds
}

// Control button component
function ControlButton({
  onClick,
  title,
  active = false,
  danger = false,
  children,
}: {
  onClick: () => void
  title: string
  active?: boolean
  danger?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick() }}
      title={title}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
        "border border-black/10 shadow-sm",
        active
          ? "bg-primary text-white"
          : danger
          ? "bg-white text-red-500 hover:bg-red-50"
          : "bg-white text-gray-700 hover:bg-gray-50"
      )}
    >
      {children}
    </button>
  )
}

export function MapViewer({ data, title, className, onBboxChange, bbox }: MapViewerProps) {
  const [basemap, setBasemap] = useState<keyof typeof BASEMAPS>('satellite')
  const [colormap, setColormap] = useState(data?.colormap || 'viridis')
  const [imageUrl, setImageUrl] = useState(data?.url || '')
  const [imageError, setImageError] = useState<string | null>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [showBasemapPicker, setShowBasemapPicker] = useState(false)
  const [showColormapPicker, setShowColormapPicker] = useState(false)
  const [opacity, setOpacity] = useState(data?.opacity ?? 0.8)
  const [inspectorActive, setInspectorActive] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<{ display_name: string; lat: string; lon: string; boundingbox: string[] }[]>([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mapRef = useRef<L.Map | null>(null)

  useEffect(() => {
    if (data?.url) {
      setImageUrl(data.url)
      setImageError(null)
    }
    if (data?.opacity !== undefined) setOpacity(data.opacity)
  }, [data?.url, data?.opacity])

  const bounds = data ? convertBounds(data.bounds) : undefined
  const resultConfig = detectResultType(data, title)
  const hasRaster = !!(data?.type === 'raster' && imageUrl && bounds)
  const hasValueRange = data?.vmin != null && data?.vmax != null

  const handleColormapChange = (newColormap: string) => {
    setColormap(newColormap)
    setShowColormapPicker(false)
    if (data?.url) {
      const baseUrl = data.url.split('?')[0]
      const params = new URLSearchParams(data.url.split('?')[1] || '')
      params.set('colormap', newColormap)
      setImageUrl(`${baseUrl}?${params.toString()}`)
    }
  }

  const handleDownload = () => {
    if (imageUrl) window.open(imageUrl, '_blank')
  }

  const handleDrawEnd = useCallback(() => setIsDrawing(false), [])
  const handleBboxChange = useCallback((b: BBox | null) => {
    onBboxChange?.(b)
  }, [onBboxChange])

  const handleSearchInput = useCallback((value: string) => {
    setSearchQuery(value)
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (!value.trim()) {
      setSearchResults([])
      return
    }
    searchTimerRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(value.trim())}`
        )
        const data = await res.json()
        setSearchResults(data)
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 400)
  }, [])

  const handleSelectPlace = useCallback((result: { lat: string; lon: string; boundingbox: string[] }) => {
    const map = mapRef.current
    if (!map) return
    const [south, north, west, east] = result.boundingbox.map(Number)
    map.fitBounds([[south, west], [north, east]], { padding: [30, 30], animate: true })
    setSearchOpen(false)
    setSearchQuery('')
    setSearchResults([])
  }, [])

  return (
    <div className={cn("relative overflow-hidden rounded-lg", className)} style={{ height: '100%', minHeight: '300px' }}>
      {/* Map fills the container */}
      <MapContainer
        center={bounds ? undefined : [20, 0]}
        zoom={bounds ? undefined : 2}
        bounds={bounds}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
        ref={mapRef}
      >
        <TileLayer url={BASEMAPS[basemap].url} attribution={BASEMAPS[basemap].attribution} />
        {bounds && <FitBounds bounds={bounds} />}

        <BboxDrawHandler
          isDrawing={isDrawing}
          bbox={bbox ?? null}
          onBboxChange={handleBboxChange}
          onDrawEnd={handleDrawEnd}
        />

        {data?.type === 'raster' && imageUrl && bounds && (
          <ImageOverlay
            url={imageUrl}
            bounds={bounds}
            opacity={opacity}
            eventHandlers={{
              error: () => setImageError('Failed to load raster image'),
              load: () => setImageError(null),
            }}
          />
        )}

        {data?.type === 'vector' && data.geojson && (
          <GeoJSON data={data.geojson} />
        )}

        {/* Pixel inspector — needs useMap() so rendered inside MapContainer */}
        {hasRaster && (
          <PixelInspector
            active={inspectorActive}
            bounds={data?.bounds}
            vmin={data?.vmin}
            vmax={data?.vmax}
            resultConfig={resultConfig}
          />
        )}
      </MapContainer>

      {/* Title overlay */}
      {title && (
        <div className="absolute left-12 top-3 z-[1000] rounded-md bg-white/90 px-3 py-1 text-sm font-medium shadow-sm backdrop-blur-sm">
          {title}
        </div>
      )}

      {/* Error overlay */}
      {imageError && (
        <div className="absolute bottom-3 left-3 z-[1000] rounded-md bg-red-500/90 px-3 py-1.5 text-xs font-medium text-white shadow">
          {imageError}
        </div>
      )}

      {/* Left controls: search + bbox draw + inspector */}
      <div className="absolute left-3 top-3 z-[1000] flex flex-col gap-1.5">
        {/* Place search */}
        <div className="relative">
          {searchOpen ? (
            <div className="flex flex-col">
              <div className="flex items-center gap-1">
                <div className="flex items-center rounded-md border border-black/10 bg-white shadow-sm">
                  <Search size={14} className="ml-2 text-gray-400" />
                  <input
                    autoFocus
                    type="text"
                    placeholder="Search place..."
                    value={searchQuery}
                    onChange={(e) => handleSearchInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') { setSearchOpen(false); setSearchQuery(''); setSearchResults([]) }
                      if (e.key === 'Enter' && searchResults.length > 0) handleSelectPlace(searchResults[0])
                    }}
                    className="w-44 bg-transparent px-2 py-1.5 text-xs outline-none"
                  />
                  {searching && (
                    <div className="mr-2 h-3 w-3 animate-spin rounded-full border-2 border-gray-300 border-t-primary" />
                  )}
                </div>
                <ControlButton onClick={() => { setSearchOpen(false); setSearchQuery(''); setSearchResults([]) }} title="Close search">
                  <X size={14} />
                </ControlButton>
              </div>
              {searchResults.length > 0 && (
                <div className="mt-1 max-h-48 w-56 overflow-y-auto rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                  {searchResults.map((r, i) => (
                    <button
                      key={i}
                      onClick={(e) => { e.stopPropagation(); handleSelectPlace(r) }}
                      className="w-full px-3 py-1.5 text-left text-xs text-gray-700 transition-colors hover:bg-gray-50"
                    >
                      <span className="line-clamp-2">{r.display_name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <ControlButton onClick={() => setSearchOpen(true)} title="Search place">
              <Search size={15} />
            </ControlButton>
          )}
        </div>

        {onBboxChange && (
          <>
            <ControlButton
              onClick={() => { setIsDrawing(!isDrawing); setInspectorActive(false) }}
              title={isDrawing ? 'Cancel drawing' : 'Draw bounding box'}
              active={isDrawing}
            >
              {isDrawing ? <Crosshair size={15} /> : <Square size={15} />}
            </ControlButton>

            {bbox && (
              <ControlButton onClick={() => onBboxChange(null)} title="Clear bounding box" danger>
                <X size={15} />
              </ControlButton>
            )}
          </>
        )}

        {hasRaster && (
          <ControlButton
            onClick={() => { setInspectorActive(!inspectorActive); setIsDrawing(false) }}
            title={inspectorActive ? 'Disable pixel inspector' : 'Inspect pixel values'}
            active={inspectorActive}
          >
            <MousePointer size={15} />
          </ControlButton>
        )}
      </div>

      {/* Bbox coordinates badge */}
      {bbox && (
        <div className="absolute bottom-3 left-1/2 z-[1000] -translate-x-1/2 rounded-full bg-white/90 px-4 py-1.5 text-xs font-medium shadow-sm backdrop-blur-sm">
          <span className="text-gray-500">BBox:</span>{' '}
          <span className="tabular-nums">
            {bbox.west.toFixed(3)}, {bbox.south.toFixed(3)}, {bbox.east.toFixed(3)}, {bbox.north.toFixed(3)}
          </span>
        </div>
      )}

      {/* Right controls: zoom, basemap, colormap, download */}
      <div className="absolute right-3 top-3 z-[1000] flex flex-col gap-1.5">
        {/* Zoom */}
        <div className="flex flex-col gap-0.5 rounded-md border border-black/10 bg-white shadow-sm">
          <button
            onClick={() => mapRef.current?.zoomIn()}
            title="Zoom in"
            className="flex h-8 w-8 items-center justify-center rounded-t-md text-gray-700 hover:bg-gray-50"
          >
            <ZoomIn size={15} />
          </button>
          <div className="mx-1.5 h-px bg-gray-200" />
          <button
            onClick={() => mapRef.current?.zoomOut()}
            title="Zoom out"
            className="flex h-8 w-8 items-center justify-center rounded-b-md text-gray-700 hover:bg-gray-50"
          >
            <ZoomOut size={15} />
          </button>
        </div>

        {/* Basemap picker */}
        <div className="relative">
          <ControlButton
            onClick={() => { setShowBasemapPicker(!showBasemapPicker); setShowColormapPicker(false) }}
            title="Change basemap"
            active={showBasemapPicker}
          >
            <Layers size={15} />
          </ControlButton>
          {showBasemapPicker && (
            <div className="absolute right-10 top-0 w-32 rounded-md border border-gray-200 bg-white py-1 shadow-lg">
              {Object.entries(BASEMAPS).map(([key, { name }]) => (
                <button
                  key={key}
                  onClick={() => { setBasemap(key as keyof typeof BASEMAPS); setShowBasemapPicker(false) }}
                  className={cn(
                    "w-full px-3 py-1.5 text-left text-xs transition-colors hover:bg-gray-50",
                    basemap === key ? "font-semibold text-primary" : "text-gray-700"
                  )}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Colormap picker — only when raster data */}
        {data?.type === 'raster' && (
          <div className="relative">
            <ControlButton
              onClick={() => { setShowColormapPicker(!showColormapPicker); setShowBasemapPicker(false) }}
              title="Change colormap"
              active={showColormapPicker}
            >
              <span className="text-[10px] font-bold leading-none">CM</span>
            </ControlButton>
            {showColormapPicker && (
              <div className="absolute right-10 top-0 w-28 rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                {COLORMAPS.map((cm) => (
                  <button
                    key={cm}
                    onClick={() => handleColormapChange(cm)}
                    className={cn(
                      "w-full px-3 py-1.5 text-left text-xs transition-colors hover:bg-gray-50",
                      colormap === cm ? "font-semibold text-primary" : "text-gray-700"
                    )}
                  >
                    {cm}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Download — only when there's an image */}
        {imageUrl && data && (
          <ControlButton onClick={handleDownload} title="Download image">
            <Download size={15} />
          </ControlButton>
        )}

        {/* Opacity slider — only when raster data */}
        {hasRaster && (
          <OpacitySlider value={opacity} onChange={setOpacity} />
        )}
      </div>

      {/* Color legend — bottom left, above error overlay */}
      {hasRaster && hasValueRange && (
        <div className="absolute bottom-10 left-3 z-[1000]">
          <ColorLegend
            vmin={data!.vmin!}
            vmax={data!.vmax!}
            colormap={colormap}
            resultConfig={resultConfig}
          />
        </div>
      )}
    </div>
  )
}
