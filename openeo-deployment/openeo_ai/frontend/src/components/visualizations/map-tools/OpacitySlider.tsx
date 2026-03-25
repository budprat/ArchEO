interface OpacitySliderProps {
  value: number
  onChange: (value: number) => void
}

export function OpacitySlider({ value, onChange }: OpacitySliderProps) {
  const pct = Math.round(value * 100)

  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-white/20 bg-black/70 px-1.5 py-2 backdrop-blur-sm">
      <span className="text-[9px] font-medium text-white/80">Opacity</span>
      <input
        type="range"
        min={0}
        max={100}
        value={pct}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        className="h-20 w-1 cursor-pointer appearance-none rounded-full bg-white/30 accent-white"
        style={{
          writingMode: 'vertical-lr',
          direction: 'rtl',
        }}
      />
      <span className="text-[9px] tabular-nums text-white/80">{pct}%</span>
    </div>
  )
}
