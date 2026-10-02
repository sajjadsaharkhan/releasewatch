import React from 'react'

/** Wording for Jev's similarity; the ring's number carries it, colour only reinforces. */
export function similarityBand(confidence) {
  if (confidence >= 0.9) return { label: 'Almost certainly the same', high: true }
  if (confidence >= 0.8) return { label: 'Likely the same', high: true }
  return { label: 'Possibly the same', high: false }
}

export function SimilarityRing({ confidence, size = 40 }) {
  const stroke = 3
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const percent = Math.round(confidence * 100)
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${percent}% similar`} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-border" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={`${c * confidence} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className={similarityBand(confidence).high ? 'stroke-amber-600 dark:stroke-amber-400' : 'stroke-zinc-400 dark:stroke-zinc-500'}
      />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
        className="fill-foreground text-[10.5px] font-semibold tabular-nums">{percent}%</text>
    </svg>
  )
}
