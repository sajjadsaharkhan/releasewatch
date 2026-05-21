import React from 'react'

export function MetaRow({ label, children }) {
  return (
    <div className="grid grid-cols-[100px_1fr] items-start gap-2 py-1.5">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 pt-0.5">{label}</div>
      <div className="text-[12.5px] min-w-0">{children}</div>
    </div>
  )
}