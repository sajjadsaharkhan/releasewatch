# Releasewatch — Design & Frontend Conventions

The rules the `frontend/` codebase actually follows, extracted from the code. Where a
convention is followed inconsistently, it is written down as the rule *plus* the drift, so
new code has one target to hit. See [Known drift](#14-known-drift) for the full list.

**Source of truth**

| Concern | File |
|---|---|
| Design tokens (CSS vars, both themes) | `frontend/src/styles/globals.css` |
| Token → Tailwind binding, font stacks, radius | `frontend/tailwind.config.js` |
| Semantic color scales (severity / status / role) | `frontend/src/lib/constants.js` |
| Class merging | `frontend/src/lib/cn.js` |
| Primitive components | `frontend/src/components/ui/` |
| Shell (sidebar, topbar, main) | `frontend/src/components/layout/` |
| Theme state + persistence | `frontend/src/context/AppContext.jsx` |

---

## 1. Design intent

Releasewatch is an **operator's tool**, not a document. Pages are scanned and acted on,
not read top to bottom. Three consequences run through every rule below:

1. **Density over air.** Base UI text is 12–13px, table rows are `py-2`, the topbar is
   `h-12`. More rows on screen beats more whitespace.
2. **State is encoded in form, not just words.** Severity, status, role, and health each
   have a fixed color and shape so a row's condition reads before it is read.
3. **The neutral surface stays quiet.** Color is reserved for meaning. Chrome —
   sidebar, topbar, cards, tables — is zinc-based and near-monochrome so the semantic
   pills are the only thing that shouts.

---

## 2. Theme system

Class-based dark mode. `darkMode: 'class'` in `tailwind.config.js`; `AppContext` adds or
removes `.dark` on `document.documentElement` and persists to `localStorage` under
`rw:theme`. **Default is light** — there is no `prefers-color-scheme` fallback, a new
visitor gets light regardless of OS setting.

Every color is an HSL triple in a CSS custom property, consumed through Tailwind's
`hsl(var(--token))` bindings. **Never write a raw neutral** (`bg-white`, `text-zinc-900`,
`border-gray-200`) for chrome — use the token.

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--background` | `0 0% 100%` | `240 10% 3.9%` | App ground, `<main>` |
| `--foreground` | `240 10% 3.9%` | `0 0% 98%` | Body text |
| `--card` | `0 0% 100%` | `240 8% 7%` | Cards, sidebar, topbar, dialogs, toasts |
| `--card-foreground` | `240 10% 3.9%` | `0 0% 98%` | Text on cards |
| `--border` | `240 5.9% 90%` | `240 5% 19%` | All hairlines, chart grid |
| `--input` | `240 5.9% 90%` | `240 5% 19%` | Field borders, switch track (off) |
| `--primary` | `240 5.9% 10%` | `221 83% 53%` | Primary buttons, badges, active accents |
| `--primary-foreground` | `0 0% 98%` | `0 0% 100%` | Text on primary |
| `--secondary` | `240 4.8% 95.9%` | `240 5% 13%` | Secondary buttons |
| `--muted` | `240 4.8% 95.9%` | `240 5% 11%` | Search field, skeletons, row hover |
| `--muted-foreground` | `240 3.8% 46.1%` | `240 5% 64.9%` | Labels, metadata, inactive nav |
| `--accent` | `240 4.8% 95.9%` | `240 5% 15%` | Hover/active fill on nav, menu items |
| `--accent-foreground` | `240 5.9% 10%` | `0 0% 98%` | Text on accent |
| `--destructive` | `0 84.2% 60.2%` | `0 62.8% 30.6%` | Destructive buttons, field errors |
| `--ring` | `240 5.9% 10%` | `221 83% 53%` | Focus ring |
| `--radius` | `0.5rem` | `0.5rem` | Base corner radius |

**The one asymmetry to know.** `--primary` is *not* a hue in light mode — it is near-black
zinc. In dark mode it becomes blue `221 83% 53%`. So `bg-primary` renders a black button
in light and a blue button in dark, and the focus ring changes color with the theme. This
is deliberate (light mode is monochrome-chrome; dark mode needs a lift off the near-black
ground), and it means **a component that reads "blue" in dark reads "black" in light** —
never rely on `primary` to signal *blueness*. Use `tone="blue"` for that.

`--background` and `--card` are the same white in light mode; separation there comes
entirely from `--border`. In dark mode the card lifts 3.1% above the ground.

Global base rules in `globals.css`:

```css
* { @apply border-border; }                       /* every border defaults to the token */
body { @apply bg-background text-foreground font-sans antialiased; }
```

### Semantic colors bypass the tokens — on purpose

Severity, status, role, health, and charts use **raw Tailwind palette colors with explicit
`dark:` variants**, not CSS vars. They encode meaning that must stay stable across themes,
and there are more of them than the token set can hold. The formula is fixed:

```
bg-{hue}-100 text-{hue}-700   dark:bg-{hue}-900/40 dark:text-{hue}-300
```

Light: 100 background / 700 text. Dark: 900 at **40% alpha** / 300 text. The alpha is what
keeps dark pills from reading as solid blocks. Any new semantic pill uses this formula.

---

## 3. Color semantics

### Severity — `SEVERITY` in `lib/constants.js`

Ordered; `order` drives sorting. Rendered by `<SeverityBadge>` as a pill with a leading dot.

| Key | Label | Hue | Dot | order |
|---|---|---|---|---|
| `blocker` | Blocker | red | `bg-red-500` | 0 |
| `critical` | Critical | orange | `bg-orange-500` | 1 |
| `major` | Major | amber | `bg-amber-500` | 2 |
| `minor` | Minor | blue | `bg-blue-400` | 3 |
| `enhancement` | Enhancement | purple | `bg-purple-400` | 4 |

Red → orange → amber is a heat ramp; blue and purple step off it because *minor* and
*enhancement* are not "less hot", they are a different kind of thing.

### Status — `STATUS` in `lib/constants.js`

Rendered by `<StatusBadge>`. Each carries an `icon` (lucide, kebab-case) for non-pill use.

| Key | Label | Hue | Icon |
|---|---|---|---|
| `new` | New | zinc | `circle` |
| `triaged` | Triaged | sky | `tag` |
| `in_progress` | In Progress | indigo | `loader` |
| `fixed` | Fixed | green | `check-circle` |
| `verified` | Verified | teal | `shield-check` |
| `closed` | Closed | zinc (dimmed: `text-zinc-500`) | `x-circle` |
| `regression` | Regression | red | `trending-down` |
| `blocked` | Blocked | orange | `circle-slash` |

`OPEN_STATUSES` — everything except `verified` and `closed` — is the canonical "still needs
work" set. Use it; do not re-enumerate the list at a call site.

### Role — `ROLE` in `lib/constants.js`

`qa` blue · `developer` violet · `cto` rose · `admin` zinc. Rendered by `<RoleBadge>`.

Route access keys off role, not off the badge: `ADMIN_ROLES = ['admin', 'cto']` gates the
Reports section in `Sidebar`, the Settings link in `Topbar`, and `<AdminRoute>` in `App.jsx`.

### Badge tones — `Badge.jsx`

`default` (zinc) · `blue` · `green` · `amber` · `red` · `purple` · `zinc` (dimmer than
default) · `orange`. Use a tone only when no severity/status/role token fits.

### MetricCard tones — `MetricCard.jsx`

`default` · `blue` · `green` · `amber` · `red` · `purple`. Each maps to two classes: an
icon-chip fill and a delta-pill fill.

### Health & trend

Health dots: `bg-green-500` / `bg-amber-500` / `bg-red-500` at `h-2.5 w-2.5`
(`h-2 w-2` when small). Trend arrows: `↑` green, `↓` red, `−` zinc-400.

### Charts (Recharts)

Fills are literal hex, chrome is tokens:

```jsx
<CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
<XAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
<Tooltip contentStyle={{
  borderRadius: 8, fontSize: 12,
  border: '1px solid hsl(var(--border))',
  backgroundColor: 'hsl(var(--card))',
}} />
<Bar dataKey={dataKey} fill={color} radius={[3, 3, 0, 0]} />
```

Rules: horizontal grid only, no axis or tick lines, 11px ticks, bars rounded on top only,
default height 180px in `<ResponsiveContainer>`, tooltip inherits card + border tokens so
it survives the theme flip. Series palette in use — `#ef4444` red, `#f59e0b` amber,
`#6366f1` indigo (default), `#3b82f6` blue, `#f97316` orange, `#22c55e`/`#10b981` green,
`#8b5cf6` violet, `#14b8a6` teal, `#ec4899` pink, `#6b7280` grey. Match the series hue to
the semantic hue whenever the series *is* a severity or status.

Empty chart state is text, not a blank frame:
`<div className="h-[180px] flex items-center justify-center text-sm text-muted-foreground">`.

### User color

Avatars fall back to `user.avatar_color`, default `#6366f1`. `getContrastColor()` in
`lib/colors.js` picks `#000000`/`#ffffff` against any user- or label-chosen hex using a
0.5 luminance threshold — use it for any text placed on arbitrary user color.

---

## 4. Typography

Three families, declared in `tailwind.config.js`:

```js
sans: ['Inter', 'Vazir', 'system-ui', 'sans-serif']
mono: ['JetBrains Mono', 'Menlo', 'monospace']
```

- **Inter** — all UI. Loaded from Google Fonts in `frontend/index.html` at weights
  400/500/600/700.
- **Vazir** — Persian fallback, self-hosted from `/fonts/` via `@font-face` in
  `globals.css` at weights 100/300/400/500/700, all `font-display: swap`. It sits *after*
  Inter, so it only renders glyphs Inter lacks.
- **JetBrains Mono** — identifiers and machine text. Weights 400/500/600.

Use `font-mono` for: issue IDs (`issue-123`), release versions, keyboard shortcut `<kbd>`,
cURL/code blocks, and toast targets. Never for prose.

### Scale in use

| Class | Where |
|---|---|
| `text-3xl font-bold tracking-tight` | MetricCard value — the only display-sized type |
| `text-2xl font-bold` | Login wordmark, release version on detail |
| `text-xl font-bold` | Page `<h1>` on dashboard-style pages |
| `text-lg font-semibold` | Page `<h1>` on list-style pages |
| `text-base font-semibold` | Dialog title |
| `text-sm` | Body, nav items, buttons (md/lg), menu items |
| `text-[13px]` | Table body — the dense-table size |
| `text-xs` | Labels, metadata, badges, descriptions, sm buttons |
| `text-[11.5px]` / `text-[11px]` | Mono issue IDs, label chips |
| `text-[10.5px]` | Table column headers |

`text-xs` (377 uses) and `text-sm` (227) carry the app; everything larger is an exception.
Pick from this table rather than inventing a step.

### Weight

`font-medium` is the default for interactive and labeled text (261 uses). `font-semibold`
for card and section titles (157). `font-bold` only for page `<h1>` and metric values (41).
`font-normal` is effectively unused — plain body text inherits.

### Eyebrow labels

`text-xs font-medium text-muted-foreground uppercase tracking-wider` — used for MetricCard
labels and collapsible sidebar section headers **only**. Table headers use a tighter
variant: `text-[10.5px] uppercase tracking-wide text-muted-foreground`.

### Form labels

Always: `block text-xs font-medium text-muted-foreground mb-1.5`
(`mb-2` when the control below is a wrapping chip group). Required fields append
`<span className="text-destructive">*</span>`. Field errors render below as
`mt-1 text-xs text-destructive`.

---

## 5. Layout & spacing

### Shell — `AppShell.jsx`

```
<div className="flex h-screen bg-background">
  <Sidebar />                          {/* w-56, hidden below lg, border-r, bg-card */}
  <div className="flex flex-1 flex-col min-w-0">
    <Topbar />                          {/* h-12 shrink-0, border-b, bg-card */}
    <main className="flex-1 overflow-y-auto scrollbar-thin"><Outlet /></main>
  </div>
</div>
```

The **page never scrolls — `<main>` does.** Anything that must stay put (table headers,
dialog headers/footers) uses `sticky` or `shrink-0` inside that scroller, not `position: fixed`.
`min-w-0` on the content column is load-bearing: without it, wide tables blow out the flex row.

### Page container

```jsx
<div className="p-6 space-y-6 max-w-{N}xl mx-auto">
  <div>
    <h1 className="text-xl font-bold">Title</h1>
    <p className="text-sm text-muted-foreground mt-1">Subtitle</p>
  </div>
  {/* sections */}
</div>
```

Width is chosen by content type: `max-w-7xl` dashboards and analytics · `max-w-6xl`
releases, contributions · `max-w-5xl` team · `max-w-4xl` settings. Full-bleed (no
`max-w`) for the dense list pages — Issues, Triage, My Issues, Deleted — where table width
is the point.

### Spacing scale

`gap-2` is the default (128 uses); `gap-1`/`gap-1.5` for icon-plus-label pairs; `gap-3`
for form fields and button rows; `gap-4` for card grids; `gap-6` for major sections.
Vertically, `space-y-6` between page sections, `space-y-4` within a section,
`space-y-0.5` between nav items. Lay siblings out with flex/grid + `gap` — do not stack
per-element margins.

Metric grids: `grid grid-cols-2 lg:grid-cols-4 gap-4`. MetricCard carries `min-h-[160px]`
so a row stays even when one card has no description.

### Responsive

One breakpoint does the real work: `lg` (1024px). Below it the sidebar is hidden
(`hidden lg:flex`) and `Topbar` swaps in a hamburger that opens a full-screen overlay
carrying the project and release switchers. `sm` and `md` only trim labels down to icons
("New issue" → `+`). There is no tablet-specific layout.

---

## 6. Radius, borders, elevation

| Radius | Applied to |
|---|---|
| `rounded-full` (121) | Badges, pills, avatars, dots, nav count bubbles, switch |
| `rounded-xl` (67) | Cards, dialogs, toasts, MetricCard, chart frames, Empty icon chip |
| `rounded-lg` (89) | Nav items, segmented control, search field, dropdown panels, icon chips |
| `rounded-md` (49) | Small buttons, close buttons, segmented items |
| `rounded-[var(--radius)]` | Button, Input, Select trigger — the token-bound 8px |

Cards are always `rounded-xl border border-border bg-card text-card-foreground shadow-sm`.

Elevation ladder: `shadow-sm` resting surfaces and default/destructive buttons ·
`shadow-md` tooltips · `shadow-lg` dropdowns, select panels, toasts · `shadow-2xl` dialog
panel. Separation comes from `border-border` first, shadow second — dark mode leans almost
entirely on the border.

### Z-index ladder

`z-50` dialog root, tooltip, mobile menu overlay · `z-[100]` portaled dropdowns, select
panels, toast stack. Overlays that must clear a dialog get `z-[100]`; nothing else does.

---

## 7. Components

### Primitives — `components/ui/`

| Component | API |
|---|---|
| `Button` | `variant`: `default` · `outline` · `ghost` · `destructive` · `secondary` · `link`; `size`: `sm` (h-8) · `md` (h-9) · `lg` (h-10) · `icon` (9×9) · `icon-sm` (8×8); `loading` renders a spinner and disables |
| `Badge` | `tone` (8 values) |
| `SeverityBadge` / `StatusBadge` / `RoleBadge` | take the raw key, fall back to a plain `<Badge>` on an unknown key |
| `Card` | `Card` · `CardHeader` · `CardTitle` · `CardDesc` · `CardBody` |
| `Input` / `Textarea` | `error` flips border and ring to destructive |
| `Select` / `SelectItem` | portaled, checkmark on selection |
| `Dropdown` | `DropdownItem` (`icon`, `destructive`) · `DropdownSep` · `DropdownLabel`; `align`, `width` |
| `Dialog` | `size`: `sm` · `md` · `lg` · `xl` · `full` |
| `Sheet` | Right-side drawer |
| `Tabs` | Underline style, optional `icon` and `badge` per option |
| `Segmented` | Pill toggle group inside a `bg-muted` track |
| `Tooltip` | 300ms open delay, `side`: top · bottom · left · right |
| `Toast` | `ToastProvider` + `useToast()`; max 3 stacked, 4000ms default |
| `Empty` | `icon` · `title` · `body` · children slot for a CTA |
| `Avatar` / `AvatarGroup` | `size` in px; group overlaps −8px, `max` then `+N` |
| `Switch` · `Slider` · `Calendar` · `DatePicker` · `Popover` · `Icon` | — |

Compose from these. A new one-off panel that is really a card, a dialog, or an empty state
should use the primitive rather than re-declaring the classes.

### Overlay convention

`Dropdown` and `Select` both: render into `document.body` via `createPortal`, position
`fixed` from `getBoundingClientRect()` with `top: rect.bottom + 4`, clamp to the viewport
with **12px padding** on both edges, and close on outside `mousedown` and on `Escape`.
Any new floating panel follows the same four rules — an absolutely-positioned menu inside
the scrolling `<main>` will clip.

### Loading, empty, error — all three, every time

- **Loading:** skeleton when the shape is known (`IssueTableSkeleton` mirrors the real
  table's columns and widths, `bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse`);
  spinner (`animate-spin rounded-full border-2 border-border border-t-primary`) for route
  and auth transitions; `<Loader2 className="animate-spin">` inline in the topbar.
- **Empty:** `<Empty>` for a whole view; a centered `py-12 text-center text-sm
  text-muted-foreground` line for a filtered-to-nothing table.
- **Error:** `toast.error(...)` — never a bare `console.error` as the only user-visible
  outcome.

---

## 8. Motion

All keyframes live in `globals.css`. Signature easing for entrances is
`cubic-bezier(0.16, 1, 0.3, 1)`; exits use `ease-in`.

| Animation | Duration | Easing |
|---|---|---|
| `toast-slide-in` / `-out` | 250ms / 200ms | signature / ease-in |
| `sheet-slide-in` / `-out` | 300ms / 250ms | signature / ease-in |
| `dialog-in` (fade + scale 0.95 + −8px) | 200ms | signature |
| `timeline-highlight` (amber flash on deep link) | 3s | ease-out, separate light/dark keyframes |
| `reaction-pop` (0.8 → 1.15 → 1) | 180ms | ease-out |
| Switch thumb | 200ms | ease-in-out |

Everything else is `transition-colors` (Tailwind's 150ms default) on hover and focus.
Motion marks state change; it never decorates.

`prefers-reduced-motion: reduce` currently disables `reaction-pop` only — see
[Known drift](#14-known-drift).

---

## 9. Iconography

**lucide-react**, 0.453. Two access paths coexist:

```jsx
import { Search, X } from 'lucide-react'   // 69 files — direct, for static icons
<Icon name="trending-down" size={16} />    // 26 files — wrapper, for dynamic names
```

The `<Icon>` wrapper converts kebab-case to PascalCase, returns `null` on an unknown name,
and warns in dev. **Use `<Icon>` whenever the name is data** (a `STATUS` token's `icon`, a
`NavItem` prop, an `Empty` icon) — that is the only path that survives a name coming from
`constants.js`. Import directly when the icon is hard-coded in the JSX.

Sizes: `size={16}` default and in nav · `size={14}` in tabs · `h-3.5 w-3.5` inside buttons
and dense rows · `h-4 w-4` in menu items and dialog close · `size={22}` in the Empty chip.
Always `shrink-0` on an icon inside a flex row.

---

## 10. Code conventions

**Exports.** Named exports for every component *except* pages, which use `export default`
(they are lazy-loaded in `App.jsx`).

**Barrels.** `ui/`, `common/`, `layout/`, `issues/`, `project/`, `releases/`, `team/` each
have an `index.js`. Deep imports (`../components/ui/Button`) are common in existing pages
and both work — prefer the barrel for multi-import call sites.

**`cn()` always.** Every `className` that is conditional or accepts an override goes
through `cn()` from `lib/cn.js` (clsx + tailwind-merge). Components take a trailing
`className` prop and pass it **last** into `cn()` so callers can override.

**Directory rules.**

| Directory | Holds |
|---|---|
| `components/ui/` | Generic, app-agnostic primitives. No domain knowledge, no API calls. |
| `components/common/` | Cross-page, domain-aware widgets — IssueTable, MetricCard, charts, switchers |
| `components/issues/`, `project/`, `releases/`, `team/` | Feature-scoped, including that feature's modals |
| `components/layout/` | Shell only |
| `pages/` | One default-exported component per route |

**`forwardRef`** on anything that wraps a focusable element — currently `Button` and
`Input`.

**Routing.** `BrowserRouter` (path-based) from `main.jsx`. Routes are `lazy()` +
`<Suspense>` with a spinner `PageFallback`. Three guards wrap route elements:
`ProtectedRoute`, `AdminRoute` (`admin`/`cto` only), `PublicRoute`.

**Filter state lives in the URL.** `IssuesPage` reads every filter and sort from
`useSearchParams` and writes back with `{ replace: true }`, omitting defaults so a clean
view has a clean URL. New list views do the same — filters must survive a refresh and be
shareable. When deriving a fetch payload from search params, depend on
`searchParams.toString()` (a stable primitive), never on a freshly-built object — that is
the documented infinite-loop trap in `IssuesPage`.

**`localStorage` keys are `rw:`-prefixed** — `rw:theme`, `rw:activeProjectId`,
`rw:activeReleaseId`, `rw:token`, `rw:refresh_token`.

**Global state** is `AppContext` (theme, active project/release, auth, modal open flags,
inbox unread count) reached via `useApp()`. Server state is `@tanstack/react-query`
(`retry: 1`, `refetchOnWindowFocus: false`). Do not put fetched lists in `AppContext`
beyond the shell-level projects/releases it already owns.

**Keyboard.** Global handlers in `App.jsx`: `⌘K`/`Ctrl+K` opens the command palette, `c`
opens New Issue (suppressed while focus is in an `input`, `textarea`, or `select`), `Esc`
closes both. Any new global shortcut needs the same input-focus guard.

---

## 11. Copy rules

- **Times** come from `lib/relTime.js` — `relTime()` for anything in a list
  ("just now", "2m ago", "3h ago", "5d ago", "2w ago", then "Jan 5"); `fullTime()` for the
  tooltip on that relative string; `formatDuration(hours)` for spans ("45m", "3h", "2d 4h").
  Never hand-roll a date format.
- **Issue identity** is `issue-{issue_number}` in `font-mono text-muted-foreground`.
- **Sentence case** for buttons, labels, and menu items — "New issue", "Sign out",
  "Create project". Not Title Case.
- **Real ellipsis** `…`, not three dots: "Search issues…", "Loading dashboard…".
- **Em dash `—`** for a missing value in a metric or field; lowercase italic
  `unassigned` for an empty assignee.
- **Buttons name the action**, and confirmation copy matches it.
- Errors say what failed in plain terms: "Failed to load dashboard", "No issues match your
  filters." No apologies.

---

## 12. Accessibility

Rules currently held:

- Focus ring is `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`
  (`ring-1` on text inputs and the Select trigger). It is theme-aware via `--ring`.
  Every new interactive element gets one.
- Disabled state is `disabled:pointer-events-none disabled:opacity-50` (inputs use
  `disabled:cursor-not-allowed`).
- Icon-only buttons carry `aria-label` ("Close", "Dismiss").
- `Switch` is a real `role="switch"` + `aria-checked` button. Toggle buttons use
  `aria-pressed`. The toast stack is `aria-live="polite"`. Decorative glyphs are
  `aria-hidden`.
- `Escape` closes every overlay — Dialog, Dropdown, Select, command palette.
- Contrast on user-chosen colors goes through `getContrastColor()`.

See [Known drift](#14-known-drift) for the gaps.

---

## 13. Scrollbars

`.scrollbar-thin` (defined in `globals.css`) on every scroll container: 6px, transparent
track, `--border` thumb that brightens to `--muted-foreground` on hover, plus Firefox
`scrollbar-width`/`scrollbar-color`. Applied to `<main>`, the sidebar nav, dialog bodies,
and select panels.

---

## 14. Known drift

Real inconsistencies in the current code. Fix opportunistically; do not propagate.

1. **Page `<h1>` size splits two ways** — `text-xl font-bold` (Dashboard, Inbox, Releases,
   Team, Settings, Contributions, Regressions) vs `text-lg font-semibold text-foreground`
   (Issues, Triage, My Issues, Deleted Issues). It tracks the dashboard/list split, so it
   is defensible, but it is not written down anywhere in code. Treat `text-xl font-bold`
   as the default and the `text-lg` variant as the dense-list exception.
2. **`src/styles/fonts.css` is dead.** Nothing imports it; its `@font-face` blocks are
   duplicated verbatim at the top of `globals.css` (which does the woff2/woff/ttf triple,
   where `fonts.css` stops at woff). Delete it or make `globals.css` `@import` it — right
   now editing the wrong one is a silent no-op.
3. **`CLAUDE.md` says hash-based routing.** `main.jsx` uses `BrowserRouter`. The only hash
   left is `window.location.hash = '/login'` in `AppContext.logout()`, which is a stale
   full-page-reload escape hatch inside a path-routed app.
4. **`CLAUDE.md` lists a `design-prototype/` directory** that no longer exists, and a
   `hooks/useTweaks.js` + `components/dev/TweaksPanel` that are not in `src/`.
5. **`Dialog` has no `role="dialog"`, no `aria-modal`, no focus trap, and no
   focus restore.** It closes on `Escape` and on backdrop click only. This is the largest
   a11y gap in the codebase.
6. **`IssueTable` rows are clickable `<tr onClick>`** with no `tabIndex`, key handler, or
   `role="button"` — the rows are unreachable by keyboard.
7. **`prefers-reduced-motion` covers `reaction-pop` only.** The toast, sheet, dialog, and
   3-second timeline-highlight animations all ignore it.
8. **`toast.error(...)` does not exist — 11 call sites are broken.** `ToastProvider`
   exposes `toast` as a plain function taking `{ title, body, target, duration }`; there
   is no `.error` on it. `DashboardPage`, `ContributionsPage`, `RegressionsPage` and
   others call `toast.error('…')` inside `.catch()` handlers, so it throws a TypeError
   into an already-rejected chain and the user sees nothing. Modals use the correct
   `toast({ title })` form. Two of those also pass `tone`, which `ToastProvider` ignores.
   **Use `toast({ title })` in new code**, and treat `.error`/`.success` as a helper that
   still needs to be written.
9. **`Icon.jsx` reads `process.env.NODE_ENV`** in a Vite app; the idiomatic guard is
   `import.meta.env.DEV`.
10. **`kebabToPascal` is duplicated** in `ui/Icon.jsx` and `ui/Tabs.jsx`.
11. **`Sidebar` imports `cn`, `ProjectSwitcher`, `activeProjectId` and `switchProject`
    and uses none of them** — leftovers from when the project switcher lived in the
    sidebar rather than the topbar. Lint noise, not a design issue.
