import React from 'react'
import { cn } from '../../lib/cn'

export function Slider({ value, onValueChange, min = 0, max = 100, step = 1, className }) {
  const [isDragging, setIsDragging] = React.useState(false)
  const trackRef = React.useRef(null)

  const percent = ((value[0] - min) / (max - min)) * 100

  const handleMouseDown = (e) => {
    setIsDragging(true)
    updateValue(e)
  }

  const updateValue = (e) => {
    if (!trackRef.current) return
    const rect = trackRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const width = rect.width
    const rawPercent = x / width
    const newValue = min + rawPercent * (max - min)
    const steppedValue = Math.round(newValue / step) * step
    const clampedValue = Math.max(min, Math.min(max, steppedValue))
    onValueChange([clampedValue])
  }

  React.useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging) updateValue(e)
    }
    const handleMouseUp = () => setIsDragging(false)

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging])

  return (
    <div className={cn('relative h-2 w-full', className)}>
      <div
        ref={trackRef}
        className="absolute inset-0 h-full bg-muted rounded-full overflow-hidden cursor-pointer"
        onMouseDown={handleMouseDown}
      >
        <div
          className="absolute inset-y-0 left-0 bg-primary rounded-full"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div
        className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-background border-2 border-primary rounded-full cursor-grab active:cursor-grabbing shadow"
        style={{ left: `calc(${percent}% - 8px)` }}
        onMouseDown={handleMouseDown}
      />
    </div>
  )
}