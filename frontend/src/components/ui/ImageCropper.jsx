import React, { useRef, useState, useEffect } from 'react'
import { cn } from '../../lib/cn'
import { Button } from './Button'
import { Slider } from './Slider'
import { X } from 'lucide-react'

export function ImageCropper({ image, onSave, onCancel }) {
  const canvasRef = useRef(null)
  const [zoom, setZoom] = useState(1)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [imageObj, setImageObj] = useState(null)
  const [containerSize, setContainerSize] = useState(300)

  useEffect(() => {
    const img = new Image()
    img.onload = () => {
      setImageObj(img)
      setContainerSize(Math.min(300, window.innerWidth - 32))
    }
    img.src = image
  }, [image])

  useEffect(() => {
    if (canvasRef.current && imageObj) {
      draw()
    }
  }, [zoom, position, imageObj, containerSize])

  const draw = () => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    canvas.width = containerSize
    canvas.height = containerSize

    ctx.fillStyle = '#1a1a1a'
    ctx.fillRect(0, 0, containerSize, containerSize)

    if (imageObj) {
      const scale = zoom * (containerSize / Math.min(imageObj.width, imageObj.height))
      const drawWidth = imageObj.width * scale
      const drawHeight = imageObj.height * scale
      const x = (containerSize - drawWidth) / 2 + position.x
      const y = (containerSize - drawHeight) / 2 + position.y

      ctx.drawImage(imageObj, x, y, drawWidth, drawHeight)
    }
  }

  const handleMouseDown = (e) => {
    setDragging(true)
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y })
  }

  const handleMouseMove = (e) => {
    if (dragging) {
      setPosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
    }
  }

  const handleMouseUp = () => {
    setDragging(false)
  }

  const handleSave = () => {
    const canvas = document.createElement('canvas')
    canvas.width = 400
    canvas.height = 400
    const ctx = canvas.getContext('2d')

    if (imageObj) {
      const scale = zoom * (containerSize / Math.min(imageObj.width, imageObj.height))
      const outputScale = 400 / containerSize
      const drawWidth = imageObj.width * scale * outputScale
      const drawHeight = imageObj.height * scale * outputScale
      const x = (400 - drawWidth) / 2 + position.x * outputScale
      const y = (400 - drawHeight) / 2 + position.y * outputScale

      ctx.drawImage(imageObj, x, y, drawWidth, drawHeight)
    }

    canvas.toBlob((blob) => {
      onSave(blob)
    }, 'image/jpeg', 0.9)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-card rounded-2xl shadow-2xl max-w-md w-full p-6 flex flex-col items-center">
        <div className="flex items-center justify-between w-full mb-4">
          <h3 className="text-sm font-semibold">Crop your photo</h3>
          <Button variant="ghost" size="icon" onClick={onCancel}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="relative mb-4 flex justify-center" style={{ width: containerSize, height: containerSize }}>
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            className="rounded-lg cursor-move border border-border"
            style={{ width: containerSize, height: containerSize }}
          />
          <div className="absolute inset-0 pointer-events-none border-2 border-primary/50 rounded-lg" style={{ margin: 'auto' }} />
        </div>

        <div className="mb-4 w-full">
          <label className="block text-xs font-medium text-muted-foreground mb-2">Zoom</label>
          <Slider
            value={[zoom]}
            onValueChange={([v]) => setZoom(v)}
            min={1}
            max={3}
            step={0.05}
            className="w-full"
          />
        </div>

        <div className="flex gap-2 w-full">
          <Button variant="outline" className="flex-1" onClick={onCancel}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={handleSave}>
            Apply
          </Button>
        </div>
      </div>
    </div>
  )
}