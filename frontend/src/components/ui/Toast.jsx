import React, { createContext, useContext, useState, useCallback, useRef } from 'react'
import { X, Send } from 'lucide-react'
import { cn } from '../../lib/cn'

const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}

let _toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    clearTimeout(timers.current[id])
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(({ title, body, target, duration = 4000 }) => {
    const id = ++_toastId
    setToasts((prev) => {
      const next = [{ id, title, body, target }, ...prev]
      return next.slice(0, 3)
    })
    timers.current[id] = setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      {/* Toast stack */}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-[100] flex flex-col-reverse gap-2 pointer-events-none"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              'toast-enter pointer-events-auto flex items-start gap-3 rounded-xl border border-border',
              'bg-card text-card-foreground shadow-lg px-4 py-3 w-80 max-w-[calc(100vw-2rem)]'
            )}
          >
            {t.target && (
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
                <Send className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              {t.title && <p className="text-sm font-semibold leading-tight">{t.title}</p>}
              {t.body && (
                <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{t.body}</p>
              )}
              {t.target && (
                <p className="mt-1 text-xs text-blue-600 dark:text-blue-400 font-mono">{t.target}</p>
              )}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="mt-0.5 shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
