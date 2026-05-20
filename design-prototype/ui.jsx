// ─── shadcn-flavored UI primitives ──────────────────────────────────────────
const { useState, useEffect, useMemo, useRef, useCallback, createContext, useContext } = React;

function cn(...args) {
  return args.filter(Boolean).join(' ');
}

// ───── Icon wrapper (use lucide global) ─────
function Icon({ name, className = '', size = 16, strokeWidth = 2 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !window.lucide) return;
    const el = ref.current;
    el.innerHTML = '';
    try {
      const icons = window.lucide.icons || window.lucide;
      // toPascalCase
      const pascal = name.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join('');
      const def = icons[pascal];
      if (!def) {
        // fallback: empty
        return;
      }
      const svg = window.lucide.createElement(def);
      svg.setAttribute('width', String(size));
      svg.setAttribute('height', String(size));
      svg.setAttribute('stroke-width', String(strokeWidth));
      el.appendChild(svg);
    } catch (e) {}
  }, [name, size, strokeWidth]);
  return <span ref={ref} className={cn('inline-flex shrink-0', className)} aria-hidden="true" />;
}

// ───── Button ─────
function Button({ children, variant = 'default', size = 'md', className = '', as: As = 'button', ...props }) {
  const base = 'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 ring-offset-bg disabled:opacity-50 disabled:pointer-events-none';
  const sizes = {
    sm: 'h-7 px-2.5 text-xs',
    md: 'h-8 px-3 text-sm',
    lg: 'h-10 px-5 text-sm',
    icon: 'h-8 w-8',
  };
  const variants = {
    default:      'bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white',
    primary:      'bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white',
    outline:      'border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-900',
    ghost:        'hover:bg-zinc-100 text-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800',
    subtle:       'bg-zinc-100 hover:bg-zinc-200 text-zinc-900 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:text-zinc-100',
    destructive:  'bg-red-600 text-white hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-500',
    success:      'bg-emerald-600 text-white hover:bg-emerald-700',
    link:         'text-blue-600 hover:underline px-0 dark:text-blue-400',
  };
  return (
    <As className={cn(base, sizes[size], variants[variant], className)} {...props}>{children}</As>
  );
}

// ───── Card ─────
function Card({ children, className = '', ...props }) {
  return (
    <div className={cn('rounded-xl border border-zinc-200 bg-white shadow-sm dark:bg-zinc-950 dark:border-zinc-800', className)} {...props}>
      {children}
    </div>
  );
}
const CardHeader = ({ children, className='' }) => <div className={cn('px-5 pt-5 pb-3', className)}>{children}</div>;
const CardTitle  = ({ children, className='' }) => <h3 className={cn('text-sm font-semibold text-zinc-900 dark:text-zinc-100', className)}>{children}</h3>;
const CardDesc   = ({ children, className='' }) => <p className={cn('text-xs text-zinc-500 dark:text-zinc-400 mt-0.5', className)}>{children}</p>;
const CardBody   = ({ children, className='' }) => <div className={cn('px-5 pb-5', className)}>{children}</div>;

// ───── Badge ─────
function Badge({ children, className = '', tone = 'default' }) {
  const tones = {
    default: 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-200 dark:ring-zinc-700',
    blue:    'bg-blue-100 text-blue-800 ring-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:ring-blue-900',
    red:     'bg-red-100 text-red-800 ring-red-200 dark:bg-red-950/60 dark:text-red-300 dark:ring-red-900',
    amber:   'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:ring-amber-900',
    green:   'bg-green-100 text-green-800 ring-green-200 dark:bg-green-950/60 dark:text-green-300 dark:ring-green-900',
    muted:   'bg-zinc-50 text-zinc-500 ring-zinc-200 dark:bg-zinc-900 dark:text-zinc-400 dark:ring-zinc-700',
  };
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset', tones[tone], className)}>
      {children}
    </span>
  );
}

// Severity / Status / Role pills — driven by data tokens
function SeverityBadge({ value, size = 'md', dot = false, className = '' }) {
  const s = SEVERITY[value]; if (!s) return null;
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-md ring-1 ring-inset font-medium',
      size === 'sm' ? 'px-1.5 py-0 text-[10.5px]' : 'px-2 py-0.5 text-[11px]',
      s.pill, className,
    )}>
      {dot && <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} />}
      {s.label}
    </span>
  );
}
function StatusBadge({ value, size = 'md', className = '' }) {
  const s = STATUS[value]; if (!s) return null;
  const icon = value === 'regression' ? 'refresh-ccw'
             : value === 'fixed'      ? 'check'
             : value === 'verified'   ? 'shield-check'
             : value === 'closed'     ? 'check-check'
             : value === 'in-progress'? 'loader-circle'
             : value === 'triaged'    ? 'split'
             :                          'circle-dashed';
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-md ring-1 ring-inset font-medium',
      size === 'sm' ? 'px-1.5 py-0 text-[10.5px]' : 'px-2 py-0.5 text-[11px]',
      s.pill, className,
    )}>
      <Icon name={icon} size={size === 'sm' ? 10 : 12} />
      {s.label}
    </span>
  );
}
function RoleBadge({ value, className = '' }) {
  const r = ROLE[value]; if (!r) return null;
  return (
    <span className={cn('inline-flex items-center rounded px-1.5 py-0 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset', r.pill, className)}>
      {r.label}
    </span>
  );
}

// ───── Avatar ─────
function Avatar({ user, size = 28, ring = false, className = '' }) {
  if (!user) {
    return <div className={cn('rounded-full bg-zinc-200 dark:bg-zinc-700', className)} style={{ width: size, height: size }} />;
  }
  const fontSize = Math.max(10, Math.round(size * 0.4));
  return (
    <div
      className={cn(
        'rounded-full flex items-center justify-center text-white font-semibold select-none',
        user.color || 'bg-zinc-500',
        ring && 'ring-2 ring-white dark:ring-zinc-950',
        className,
      )}
      style={{ width: size, height: size, fontSize, lineHeight: 1 }}
      title={user.name}
    >
      {user.initials}
    </div>
  );
}

// ───── Input / Textarea / Select ─────
function Input({ className = '', ...props }) {
  return (
    <input
      className={cn('h-8 w-full rounded-md border border-zinc-200 bg-white px-2.5 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900/10 dark:bg-zinc-950 dark:border-zinc-800 dark:placeholder:text-zinc-500 dark:focus:ring-zinc-300/20', className)}
      {...props}
    />
  );
}
function Textarea({ className = '', ...props }) {
  return (
    <textarea
      className={cn('w-full rounded-md border border-zinc-200 bg-white px-2.5 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900/10 dark:bg-zinc-950 dark:border-zinc-800 dark:placeholder:text-zinc-500', className)}
      {...props}
    />
  );
}
function NativeSelect({ className = '', children, ...props }) {
  return (
    <select
      className={cn('h-8 rounded-md border border-zinc-200 bg-white px-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900/10 dark:bg-zinc-950 dark:border-zinc-800', className)}
      {...props}
    >{children}</select>
  );
}

// ───── Switch ─────
function Switch({ checked, onChange, disabled, className = '' }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange && onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors',
        checked ? 'bg-zinc-900 dark:bg-zinc-100' : 'bg-zinc-200 dark:bg-zinc-700',
        disabled && 'opacity-50 cursor-not-allowed', className,
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform',
          checked ? 'translate-x-4' : 'translate-x-0.5',
          'dark:bg-zinc-900',
          checked && 'dark:bg-zinc-900',
        )}
      />
    </button>
  );
}

// ───── Tabs ─────
function Tabs({ value, onValueChange, options, className = '' }) {
  return (
    <div className={cn('inline-flex items-center rounded-md bg-zinc-100 p-0.5 dark:bg-zinc-800', className)}>
      {options.map(o => (
        <button
          key={o.value}
          onClick={() => onValueChange(o.value)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded px-2.5 h-7 text-xs font-medium transition-colors',
            value === o.value
              ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-950 dark:text-zinc-100'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200',
          )}
        >
          {o.icon && <Icon name={o.icon} size={12} />}
          {o.label}
          {o.badge != null && (
            <span className={cn('ml-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-semibold',
              value === o.value ? 'bg-zinc-900 text-white dark:bg-zinc-200 dark:text-zinc-900' : 'bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200')}>{o.badge}</span>
          )}
        </button>
      ))}
    </div>
  );
}

// ───── Segmented control ─────
function Segmented({ value, onChange, options, size = 'md', className = '' }) {
  const sz = size === 'sm' ? 'h-7 text-xs' : 'h-8 text-sm';
  return (
    <div className={cn('inline-flex rounded-md border border-zinc-200 dark:border-zinc-800 overflow-hidden', sz, className)}>
      {options.map((o, i) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'px-3 font-medium transition-colors',
            i > 0 && 'border-l border-zinc-200 dark:border-zinc-800',
            value === o.value
              ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
              : 'bg-white text-zinc-700 hover:bg-zinc-50 dark:bg-zinc-950 dark:text-zinc-300 dark:hover:bg-zinc-900',
          )}
        >{o.label}</button>
      ))}
    </div>
  );
}

// ───── Tooltip (lightweight) ─────
function Tooltip({ content, children, side = 'top' }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      {children}
      {open && (
        <span
          className={cn(
            'pointer-events-none absolute z-50 whitespace-nowrap rounded-md bg-zinc-900 px-2 py-1 text-[11px] text-white shadow-md dark:bg-zinc-100 dark:text-zinc-900',
            side === 'top' && 'bottom-full mb-1.5 left-1/2 -translate-x-1/2',
            side === 'bottom' && 'top-full mt-1.5 left-1/2 -translate-x-1/2',
            side === 'right' && 'left-full ml-1.5 top-1/2 -translate-y-1/2',
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}

// ───── Dropdown menu ─────
function Dropdown({ trigger, children, align = 'right', width = 200 }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function handler(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);
  return (
    <div className="relative inline-block" ref={ref}>
      <div onClick={() => setOpen(o => !o)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute z-40 mt-1.5 rounded-lg border border-zinc-200 bg-white shadow-lg dark:bg-zinc-950 dark:border-zinc-800 py-1',
            align === 'right' ? 'right-0' : 'left-0',
          )}
          style={{ width }}
          onClick={(e) => e.stopPropagation()}
        >
          {typeof children === 'function' ? children({ close: () => setOpen(false) }) : children}
        </div>
      )}
    </div>
  );
}
function DropdownItem({ children, onClick, icon, danger, className = '', disabled }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-2.5 py-1.5 text-sm w-full text-left',
        danger ? 'text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30' : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800',
        disabled && 'opacity-50 cursor-not-allowed', className,
      )}
    >
      {icon && <Icon name={icon} size={14} />}
      {children}
    </button>
  );
}
const DropdownSep = () => <div className="h-px bg-zinc-200 my-1 dark:bg-zinc-800" />;
const DropdownLabel = ({ children }) => <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{children}</div>;

// ───── Sheet / Drawer ─────
function Sheet({ open, onClose, side = 'right', width = 720, children }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose && onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[1px]" onClick={onClose} />
      <div
        className={cn(
          'absolute top-0 bottom-0 bg-white dark:bg-zinc-950 shadow-2xl flex flex-col',
          side === 'right' ? 'right-0 drawer-in' : 'left-0',
        )}
        style={{ width }}
      >
        {children}
      </div>
    </div>
  );
}

// ───── Dialog (modal) ─────
function Dialog({ open, onClose, children, width = 640 }) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose && onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[8vh]">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative rounded-xl bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 shadow-2xl max-h-[84vh] overflow-hidden flex flex-col" style={{ width }}>
        {children}
      </div>
    </div>
  );
}

// ───── Toast / Sonner ─────
const ToastContext = createContext(null);
function useToast() { return useContext(ToastContext); }
function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((toast) => {
    const id = Math.random().toString(36).slice(2);
    setItems(prev => [...prev, { id, ...toast }]);
    setTimeout(() => setItems(prev => prev.filter(t => t.id !== id)), toast.duration || 4200);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-[360px]">
        {items.map(t => <ToastCard key={t.id} toast={t} />)}
      </div>
    </ToastContext.Provider>
  );
}
function ToastCard({ toast }) {
  // toast: { kind, title, body, tg, target, warn }
  return (
    <div className={cn(
      'toast-in rounded-xl border bg-white dark:bg-zinc-950 shadow-lg px-3.5 py-3 flex items-start gap-3',
      toast.warn ? 'border-amber-300 dark:border-amber-800' : 'border-zinc-200 dark:border-zinc-800',
    )}>
      <div className={cn('mt-0.5 h-7 w-7 rounded-lg flex items-center justify-center shrink-0',
        toast.warn ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                   : 'bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300')}>
        <Icon name={toast.warn ? 'triangle-alert' : 'send'} size={14} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          {toast.warn ? 'Telegram — not delivered' : 'Telegram notification sent'}
        </div>
        <div className="text-sm text-zinc-900 dark:text-zinc-100 font-medium leading-snug mt-0.5">
          {toast.title}
        </div>
        {toast.body && (
          <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 leading-snug">{toast.body}</div>
        )}
        {toast.target && (
          <div className="mt-1.5 text-[11px] text-zinc-500 dark:text-zinc-400 font-mono">→ {toast.target}</div>
        )}
      </div>
    </div>
  );
}

// ───── Empty state ─────
function Empty({ icon = 'inbox', title, body, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="h-10 w-10 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-500 mb-3">
        <Icon name={icon} size={18} />
      </div>
      <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</div>
      {body && <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 max-w-sm">{body}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

Object.assign(window, {
  cn, Icon, Button, Card, CardHeader, CardTitle, CardDesc, CardBody,
  Badge, SeverityBadge, StatusBadge, RoleBadge, Avatar,
  Input, Textarea, NativeSelect, Switch, Tabs, Segmented,
  Tooltip, Dropdown, DropdownItem, DropdownSep, DropdownLabel,
  Sheet, Dialog, ToastContext, useToast, ToastProvider, Empty,
});
