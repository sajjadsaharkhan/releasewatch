// ─── All remaining screens: Dashboard, Issues, Triage, Regressions,
//     Releases, Reports, Settings, Team, New Issue modal ────────────────────

const _R = window.Recharts;

// ─────────────────────────────────────────────────────────────────────────
//  DASHBOARD
// ─────────────────────────────────────────────────────────────────────────
function DashboardScreen({ openIssue }) {
  const totalBlockers = MOCK_ISSUES.filter(i => i.severity === 'blocker' && i.status !== 'verified' && i.status !== 'closed').length;
  const totalCriticals = MOCK_ISSUES.filter(i => i.severity === 'critical' && i.status !== 'verified' && i.status !== 'closed').length;
  const totalOpen = MOCK_ISSUES.filter(i => i.status !== 'verified' && i.status !== 'closed').length;
  const regressionRate = 23;

  return (
    <div className="px-7 py-6">
      <div className="flex items-end justify-between mb-5">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Release health · today</div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">Dashboard</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm"><Icon name="download" size={12} /> Export</Button>
          <Button variant="outline" size="sm"><Icon name="bell" size={12} /> Subscribe to digest</Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <MetricCard label="Open blockers"   value={totalBlockers}   tone="red"   sub="across 3 active releases" icon="octagon-alert"  trend={{ dir: 'up', value: '+1 today' }} />
        <MetricCard label="Open criticals"  value={totalCriticals}  tone="amber" sub="of which 3 in v2.4.1"      icon="flame"          trend={{ dir: 'flat', value: 'no change' }} />
        <MetricCard label="Total open"      value={totalOpen}       sub="filed in last 7 days"                    icon="bug"            trend={{ dir: 'down', value: '−3 vs yesterday' }} />
        <MetricCard label="Regression rate" value={regressionRate + '%'} tone="amber" sub="of closed bugs returned"   icon="refresh-ccw"   trend={{ dir: 'up', value: '+5 pts' }} />
      </div>

      <div className="grid grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4 min-w-0">
          <div>
            <div className="flex items-end justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Release health</h3>
                <p className="text-[12px] text-zinc-500 dark:text-zinc-400">All projects · all active releases</p>
              </div>
              <Segmented size="sm" value="active" onChange={() => {}} options={[{ value: 'active', label: 'Active' }, { value: 'all', label: 'All' }]} />
            </div>
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
              {MOCK_RELEASES.filter(r => r.status === 'active').map(r => {
                const proj = MOCK_PROJECTS.find(p => p.id === r.projectId);
                const healthTone = r.blockers > 0 ? 'red' : r.criticals > 0 ? 'amber' : 'green';
                const healthLabel = r.blockers > 0 ? 'Blocked' : r.criticals > 0 ? 'At risk' : 'On track';
                const pct = Math.round((r.fixed / r.total) * 100);
                return (
                  <Card key={r.id} className="p-4 hover:shadow-md transition-shadow flex flex-col">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="h-7 w-7 rounded-md bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-[12px] font-bold shrink-0">{proj.name[0]}</div>
                        <div className="min-w-0">
                          <div className="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100 truncate">{proj.name}</div>
                          <div className="text-[11px] text-zinc-500 font-mono">{r.version}</div>
                        </div>
                      </div>
                      <Badge tone={healthTone}>
                        <span className={cn('h-1.5 w-1.5 rounded-full', healthTone === 'red' ? 'bg-red-500' : healthTone === 'amber' ? 'bg-amber-500' : 'bg-emerald-500')} />
                        {healthLabel}
                      </Badge>
                    </div>

                    <div className="mt-1.5 grid grid-cols-3 gap-1 text-center">
                      <DashStat label="Blockers" value={r.blockers || '—'} tone={r.blockers > 0 ? 'red' : 'default'} />
                      <DashStat label="Criticals" value={r.criticals || '—'} tone={r.criticals > 0 ? 'amber' : 'default'} />
                      <DashStat label="Regr."     value={r.regressionRate + '%'} tone={r.regressionRate > 20 ? 'amber' : 'default'} />
                    </div>

                    <div className="mt-3">
                      <div className="flex items-center justify-between text-[11px] text-zinc-500 mb-1">
                        <span>Progress</span>
                        <span className="tabular-nums"><span className="text-emerald-600 dark:text-emerald-400 font-semibold">{r.fixed}</span> / {r.total} fixed</span>
                      </div>
                      <div className="h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                        <div className={cn('h-full rounded-full', r.blockers > 0 ? 'bg-red-500' : 'bg-emerald-500')} style={{ width: pct + '%' }} />
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between gap-2">
                      <span className="text-[11px] text-zinc-500 inline-flex items-center gap-1"><Icon name="activity" size={11} /> {r.lastActivity}</span>
                      <Button size="sm" variant={r.blockers === 0 ? 'success' : 'outline'} disabled={r.blockers > 0}>
                        {r.blockers > 0 ? <><Icon name="octagon-alert" size={11} /> No-Go</> : <><Icon name="check" size={11} /> Approve</>}
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Live blockers</CardTitle>
              <CardDesc>Release-blocking issues across all projects</CardDesc>
            </CardHeader>
            <CardBody className="pt-0 pb-3">
              <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                {MOCK_ISSUES.filter(i => i.releaseBlocker).map(i => {
                  const a = userById(i.assignee); const r = userById(i.reporter);
                  return (
                    <li key={i.id}
                      onClick={() => openIssue(i)}
                      className="flex items-center gap-3 py-2.5 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/40 -mx-3 px-3 rounded">
                      <SeverityBadge value={i.severity} dot />
                      <span className="font-mono text-[11px] text-zinc-500">{i.id}</span>
                      <span className="text-[13.5px] text-zinc-900 dark:text-zinc-100 truncate flex-1">{i.title}</span>
                      <span className="text-[11px] text-zinc-500 font-mono">{i.release}</span>
                      {a ? <Avatar user={a} size={22} /> : <span className="text-[11px] text-zinc-400">unassigned</span>}
                      <span className="text-[11px] text-zinc-500 w-8 text-right">{i.age}</span>
                    </li>
                  );
                })}
              </ul>
            </CardBody>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Activity</CardTitle>
              <button className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">View all</button>
            </div>
            <CardDesc>Live across your team</CardDesc>
          </CardHeader>
          <CardBody className="pt-0">
            <ul className="space-y-3">
              {MOCK_ACTIVITY.map(a => {
                const u = userById(a.actor);
                const dot = a.type === 'fixed' ? 'bg-emerald-500'
                          : a.type === 'filed' ? 'bg-blue-500'
                          : a.type === 'regression' ? 'bg-red-500'
                          : a.type === 'verified' ? 'bg-green-600'
                          : 'bg-zinc-400';
                return (
                  <li key={a.id} className="flex items-start gap-2.5 text-[12.5px]">
                    <Avatar user={u} size={22} />
                    <div className="min-w-0 flex-1 leading-snug text-zinc-700 dark:text-zinc-200">
                      <span className="font-medium text-zinc-900 dark:text-zinc-100">{u?.name}</span>
                      {' '}{a.verb}{' '}
                      <span className="font-mono text-[11px] text-blue-600 dark:text-blue-400">{a.target}</span>
                      {a.extra && <span className="text-zinc-500"> {a.extra}</span>}
                      <div className="text-[10.5px] text-zinc-400 mt-0.5 flex items-center gap-1">
                        <span className={cn('h-1.5 w-1.5 rounded-full', dot)} />
                        {a.time}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  ISSUE LIST + filters + board view
// ─────────────────────────────────────────────────────────────────────────
function IssuesScreen({ openIssue, view = 'all' }) {
  const { issues, query } = useApp();
  const [filter, setFilter] = useState({ severity: 'all', status: 'all', release: 'all', assignee: 'all' });
  const [viewMode, setViewMode] = useState('table');
  const [sort, setSort] = useState('newest');

  const filtered = useMemo(() => {
    return issues.filter(i => {
      if (view === 'triage' && i.assignee) return false;
      if (view === 'assigned' && i.assignee !== 'u7') return false;
      if (filter.severity !== 'all' && i.severity !== filter.severity) return false;
      if (filter.status !== 'all' && i.status !== filter.status) return false;
      if (filter.assignee !== 'all') {
        if (filter.assignee === 'unassigned') { if (i.assignee) return false; }
        else if (i.assignee !== filter.assignee) return false;
      }
      if (query) {
        const q = query.toLowerCase();
        if (!i.title.toLowerCase().includes(q) && !i.id.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [issues, filter, query, view]);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-7 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {view === 'triage' ? 'Triage Queue' : view === 'assigned' ? 'My Assigned' : 'All Issues'}
          </h1>
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400">{filtered.length} of {issues.length} issues</p>
        </div>
        <div className="flex items-center gap-2">
          <Segmented size="sm" value={viewMode} onChange={setViewMode}
            options={[{ value: 'table', label: 'Table' }, { value: 'board', label: 'Board' }]} />
          <Button variant="outline" size="sm"><Icon name="download" size={12} /> Export</Button>
        </div>
      </div>

      <div className="px-7 py-3 border-b border-zinc-200 dark:border-zinc-800 flex flex-wrap items-center gap-2 bg-zinc-50/60 dark:bg-zinc-900/40">
        <FilterDropdown icon="alert-octagon" label="Severity"
          value={filter.severity === 'all' ? 'Any' : SEVERITY[filter.severity].label}
          options={[{ value: 'all', label: 'Any' }, ...Object.keys(SEVERITY).map(k => ({ value: k, label: SEVERITY[k].label }))]}
          onChange={(v) => setFilter(f => ({ ...f, severity: v }))} />
        <FilterDropdown icon="circle-dashed" label="Status"
          value={filter.status === 'all' ? 'Any' : STATUS[filter.status].label}
          options={[{ value: 'all', label: 'Any' }, ...Object.keys(STATUS).map(k => ({ value: k, label: STATUS[k].label }))]}
          onChange={(v) => setFilter(f => ({ ...f, status: v }))} />
        <FilterDropdown icon="user" label="Assignee"
          value={filter.assignee === 'all' ? 'Any' : filter.assignee === 'unassigned' ? 'Unassigned' : userById(filter.assignee)?.name}
          options={[{ value: 'all', label: 'Any' }, { value: 'unassigned', label: 'Unassigned' }, ...MOCK_TEAM.map(u => ({ value: u.id, label: u.name }))]}
          onChange={(v) => setFilter(f => ({ ...f, assignee: v }))} />
        <FilterChipStatic icon="tag" label="Release" value="v2.4.1" />
        <FilterChipStatic icon="hash" label="Labels" value="Any" />
        <button className="text-[12px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 px-2">+ Add filter</button>
        <div className="ml-auto flex items-center gap-2">
          <Icon name="arrow-up-down" size={12} className="text-zinc-400" />
          <NativeSelect value={sort} onChange={(e) => setSort(e.target.value)} className="text-[12px]">
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="severity">Severity</option>
            <option value="updated">Last updated</option>
          </NativeSelect>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {viewMode === 'table' ? <IssueTable issues={filtered} onOpen={openIssue} /> : <IssueBoard issues={filtered} onOpen={openIssue} />}
      </div>
    </div>
  );
}

function FilterChipStatic({ icon, label, value }) {
  return (
    <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 text-[12px]">
      <Icon name={icon} size={12} className="text-zinc-500" />
      <span className="text-zinc-500">{label}:</span>
      <span className="font-medium text-zinc-800 dark:text-zinc-100">{value}</span>
      <Icon name="chevron-down" size={11} className="text-zinc-400" />
    </button>
  );
}

function DashStat({ label, value, tone = 'default' }) {
  const tones = {
    default: 'text-zinc-900 dark:text-zinc-100',
    red:     'text-red-600 dark:text-red-400',
    amber:   'text-amber-600 dark:text-amber-400',
    green:   'text-emerald-600 dark:text-emerald-400',
  };
  return (
    <div className="rounded-md bg-zinc-50 dark:bg-zinc-900 px-2 py-1.5">
      <div className="text-[9.5px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className={cn('text-[14px] font-semibold tabular-nums', tones[tone])}>{value}</div>
    </div>
  );
}

function FilterDropdown({ icon, label, value, options, onChange }) {
  return (
    <Dropdown width={200}
      trigger={
        <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 text-[12px]">
          <Icon name={icon} size={12} className="text-zinc-500" />
          <span className="text-zinc-500">{label}:</span>
          <span className="font-medium text-zinc-800 dark:text-zinc-100">{value}</span>
          <Icon name="chevron-down" size={11} className="text-zinc-400" />
        </button>
      }
    >
      {({ close }) => options.map(o => (
        <DropdownItem key={o.value} onClick={() => { onChange(o.value); close(); }}>{o.label}</DropdownItem>
      ))}
    </Dropdown>
  );
}

function IssueTable({ issues, onOpen, hideRelease = false, hideReporter = false }) {
  return (
    <table className="w-full text-[13px]">
      <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-white/95 dark:bg-zinc-950/95 backdrop-blur">
        <tr>
          <th className="text-left font-medium px-7 py-2.5 w-[90px]">#</th>
          <th className="text-left font-medium px-2 py-2.5">Title</th>
          <th className="text-left font-medium px-2 py-2.5 w-[110px]">Severity</th>
          <th className="text-left font-medium px-2 py-2.5 w-[120px]">Status</th>
          <th className="text-left font-medium px-2 py-2.5 w-[140px]">Assignee</th>
          {!hideReporter && <th className="text-left font-medium px-2 py-2.5 w-[170px]">Reporter</th>}
          {!hideRelease && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Release</th>}
          <th className="text-left font-medium px-2 py-2.5 w-[64px]">Regr.</th>
          <th className="text-right font-medium px-7 py-2.5 w-[80px]">Age</th>
        </tr>
      </thead>
      <tbody>
        {issues.map(i => {
          const a = userById(i.assignee); const r = userById(i.reporter);
          return (
            <tr key={i.id} onClick={() => onOpen(i)}
              className="border-b border-zinc-100 dark:border-zinc-900 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
              <td className="px-7 py-2 font-mono text-[11.5px] text-zinc-500">{i.id}</td>
              <td className="px-2 py-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-zinc-900 dark:text-zinc-100 font-medium truncate max-w-[420px]">{i.title}</span>
                  {i.labels.slice(0,1).map(l => <LabelChip key={l}>{l}</LabelChip>)}
                  {i.releaseBlocker && <Badge tone="red"><Icon name="octagon-alert" size={10} /> Blocker</Badge>}
                </div>
              </td>
              <td className="px-2 py-2"><SeverityBadge value={i.severity} dot /></td>
              <td className="px-2 py-2"><StatusBadge value={i.status} /></td>
              <td className="px-2 py-2">
                {a ? (
                  <div className="flex items-center gap-1.5">
                    <Avatar user={a} size={20} />
                    <span className="text-zinc-700 dark:text-zinc-300 truncate">{a.name}</span>
                  </div>
                ) : <span className="text-[11px] text-zinc-400 italic">unassigned</span>}
              </td>
              {!hideReporter && (
                <td className="px-2 py-2">
                  <div className="flex items-center gap-1.5">
                    <Avatar user={r} size={20} />
                    <span className="text-zinc-700 dark:text-zinc-300 truncate">{r?.name}</span>
                    <RoleBadge value={i.reporterRole} />
                  </div>
                </td>
              )}
              {!hideRelease && <td className="px-2 py-2 font-mono text-zinc-600 dark:text-zinc-300">{i.release}</td>}
              <td className="px-2 py-2">
                {i.regressions > 0
                  ? <span className="inline-flex items-center gap-0.5 text-red-600 dark:text-red-400 text-[12px] font-semibold"><Icon name="refresh-ccw" size={11} />{i.regressions}</span>
                  : <span className="text-zinc-300">—</span>}
              </td>
              <td className="px-7 py-2 text-right tabular-nums text-zinc-500">{i.age}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function IssueBoard({ issues, onOpen }) {
  const cols = ['new', 'triaged', 'in-progress', 'fixed', 'verified'];
  return (
    <div className="px-7 py-5 grid gap-3" style={{ gridTemplateColumns: `repeat(${cols.length}, minmax(220px, 1fr))` }}>
      {cols.map(s => {
        const list = issues.filter(i => i.status === s);
        return (
          <div key={s} className="flex flex-col min-h-0">
            <div className="px-1 pb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5"><StatusBadge value={s} size="sm" /><span className="text-[11px] text-zinc-500 tabular-nums">{list.length}</span></div>
              <button className="h-6 w-6 rounded text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center"><Icon name="plus" size={12} /></button>
            </div>
            <div className="flex-1 space-y-2 min-h-[120px] rounded-lg bg-zinc-50 dark:bg-zinc-900/40 p-2">
              {list.map(i => {
                const a = userById(i.assignee);
                return (
                  <button key={i.id} onClick={() => onOpen(i)}
                    className="w-full text-left rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3 hover:border-zinc-400 dark:hover:border-zinc-600 transition-colors">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-[10.5px] text-zinc-500">{i.id}</span>
                      <SeverityBadge value={i.severity} size="sm" />
                    </div>
                    <div className="text-[12.5px] font-medium text-zinc-900 dark:text-zinc-100 leading-snug mb-2">{i.title}</div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1">
                        {i.labels.slice(0,2).map(l => <LabelChip key={l}>{l}</LabelChip>)}
                      </div>
                      {a && <Avatar user={a} size={18} />}
                    </div>
                    {i.regressions > 0 && (
                      <div className="mt-1.5 text-[10.5px] text-red-600 dark:text-red-400 inline-flex items-center gap-0.5">
                        <Icon name="refresh-ccw" size={10} /> regressed {i.regressions}×
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  TRIAGE QUEUE
// ─────────────────────────────────────────────────────────────────────────

const TRIAGE_MEDIA = [
  {
    id: 'm1', kind: 'image', label: '500-response.png',
    size: '248 KB', meta: '1284 × 812', captured: 'just now · staging-2',
  },
  {
    id: 'm2', kind: 'video', label: 'screen-rec.mp4',
    size: '4.1 MB', meta: '1m 12s · 1080p', captured: 'reporter · iPhone 14 Pro',
  },
  {
    id: 'm3', kind: 'file', label: 'trace.log',
    size: '32 KB', meta: '412 lines', captured: 'wallet-svc · pod-7f4',
  },
];

function TriageMediaPreview() {
  const [activeId, setActiveId] = useState('m1');
  const [saved, setSaved] = useState(false);
  const toast = useToast();
  const active = TRIAGE_MEDIA.find(m => m.id === activeId);

  const download = (e) => {
    e.stopPropagation();
    toast({ title: `Downloading ${active.label}`, body: `${active.size} · saving to ~/Downloads`, target: '' });
    setSaved(true);
    setTimeout(() => setSaved(false), 1400);
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden bg-white dark:bg-zinc-950">
      {/* hero preview */}
      <div className="relative bg-zinc-50 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <MediaPreviewSurface media={active} />

        {/* overlay header */}
        <div className="absolute top-2 left-2 right-2 flex items-center gap-1.5 pointer-events-none">
          <div className="pointer-events-auto inline-flex items-center gap-1.5 h-6 px-2 rounded-md bg-white/95 dark:bg-zinc-950/90 border border-zinc-200 dark:border-zinc-800 backdrop-blur">
            <Icon name={active.kind === 'image' ? 'image' : active.kind === 'video' ? 'play' : 'file-text'} size={11} className="text-zinc-600 dark:text-zinc-300" />
            <span className="text-[11px] font-mono text-zinc-800 dark:text-zinc-100 max-w-[150px] truncate">{active.label}</span>
          </div>
          <div className="ml-auto flex items-center gap-1 pointer-events-auto">
            <button
              title="Open full"
              className="h-6 w-6 inline-flex items-center justify-center rounded-md bg-white/95 dark:bg-zinc-950/90 border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 backdrop-blur">
              <Icon name="maximize-2" size={11} />
            </button>
            <button
              onClick={download}
              title={`Download ${active.label}`}
              className="inline-flex items-center gap-1 h-6 px-2 rounded-md bg-zinc-900 text-white text-[11px] font-medium hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white shadow-sm">
              <Icon name={saved ? 'check' : 'download'} size={11} />
              {saved ? 'Saved' : 'Download'}
            </button>
          </div>
        </div>
      </div>

      {/* meta strip */}
      <div className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-zinc-600 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
        <span className="font-medium text-zinc-700 dark:text-zinc-200">{active.size}</span>
        <span className="text-zinc-300 dark:text-zinc-700">·</span>
        <span>{active.meta}</span>
        <span className="text-zinc-300 dark:text-zinc-700">·</span>
        <span className="truncate">{active.captured}</span>
      </div>

      {/* thumbnail strip */}
      <div className="grid grid-cols-3 gap-1 p-1">
        {TRIAGE_MEDIA.map(m => (
          <button
            key={m.id}
            onClick={() => setActiveId(m.id)}
            className={cn(
              'group rounded-md p-1.5 flex items-center gap-2 text-left transition-colors min-w-0',
              activeId === m.id
                ? 'bg-zinc-100 dark:bg-zinc-800'
                : 'hover:bg-zinc-50 dark:hover:bg-zinc-900'
            )}>
            <div className={cn(
              'h-7 w-7 rounded flex items-center justify-center shrink-0 border',
              activeId === m.id
                ? 'bg-white dark:bg-zinc-950 border-zinc-300 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100'
                : 'bg-zinc-100 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400'
            )}>
              <Icon name={m.kind === 'image' ? 'image' : m.kind === 'video' ? 'play' : 'file-text'} size={12} />
            </div>
            <div className="min-w-0">
              <div className={cn(
                'text-[11.5px] font-medium truncate',
                activeId === m.id ? 'text-zinc-900 dark:text-zinc-100' : 'text-zinc-700 dark:text-zinc-300'
              )}>{m.label}</div>
              <div className="text-[10px] text-zinc-500 truncate">{m.size}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function MediaPreviewSurface({ media }) {
  if (media.kind === 'image') {
    return (
      <div className="aspect-[16/9] w-full relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-100 to-zinc-200 dark:from-zinc-900 dark:to-zinc-950">
          <div className="h-5 border-b border-zinc-300/70 dark:border-zinc-700/60 bg-white/60 dark:bg-zinc-900/60 flex items-center gap-1 px-2">
            <span className="h-1.5 w-1.5 rounded-full bg-red-400/80" />
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400/80" />
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400/80" />
            <div className="ml-2 h-2.5 rounded-sm bg-zinc-200 dark:bg-zinc-800 flex-1 max-w-[180px]" />
          </div>
          <div className="absolute left-1/2 top-[54%] -translate-x-1/2 -translate-y-1/2 w-[72%] rounded-md bg-white dark:bg-zinc-900 shadow-lg ring-1 ring-zinc-200 dark:ring-zinc-800 overflow-hidden">
            <div className="px-2.5 py-1.5 bg-red-50 dark:bg-red-950/40 border-b border-red-200/70 dark:border-red-900/50 flex items-center gap-1.5">
              <Icon name="triangle-alert" size={11} className="text-red-600 dark:text-red-400" />
              <span className="text-[10.5px] font-mono font-semibold text-red-700 dark:text-red-300">500 Internal Server Error</span>
              <span className="ml-auto text-[9.5px] font-mono text-red-500/80 hidden sm:inline">POST /wallet/transfer</span>
            </div>
            <div className="px-2.5 py-2 space-y-0.5 font-mono text-[9.5px] leading-snug text-zinc-700 dark:text-zinc-300">
              <div><span className="text-zinc-400">{'{'}</span></div>
              <div className="pl-3"><span className="text-blue-600 dark:text-blue-400">"error"</span>: <span className="text-emerald-600 dark:text-emerald-400">"balance_inconsistent"</span>,</div>
              <div className="pl-3"><span className="text-blue-600 dark:text-blue-400">"trace_id"</span>: <span className="text-emerald-600 dark:text-emerald-400">"wlt-7f4-aGc1z"</span>,</div>
              <div className="pl-3"><span className="text-blue-600 dark:text-blue-400">"debit_count"</span>: <span className="text-amber-600 dark:text-amber-400">2</span></div>
              <div><span className="text-zinc-400">{'}'}</span></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (media.kind === 'video') {
    return (
      <div className="aspect-[16/9] w-full relative bg-zinc-900 dark:bg-black overflow-hidden">
        <div className="absolute inset-0 opacity-70" style={{
          background: 'radial-gradient(ellipse at 30% 40%, rgba(99,102,241,0.4), transparent 60%), radial-gradient(ellipse at 70% 70%, rgba(244,63,94,0.28), transparent 55%)'
        }} />
        <div className="absolute inset-0 grid grid-cols-12 grid-rows-7 opacity-20">
          {Array.from({ length: 84 }).map((_, i) => <div key={i} className="border border-white/5" />)}
        </div>
        <div className="absolute inset-0 flex items-center justify-center">
          <button className="h-12 w-12 rounded-full bg-white/95 text-zinc-900 shadow-xl flex items-center justify-center hover:scale-105 transition-transform">
            <Icon name="play" size={20} className="ml-0.5" />
          </button>
        </div>
        <div className="absolute bottom-2 left-2 right-2 flex items-center gap-2 text-white">
          <span className="font-mono text-[10px] tabular-nums">0:00</span>
          <div className="flex-1 h-1 rounded-full bg-white/20 overflow-hidden">
            <div className="h-full w-[18%] bg-white rounded-full" />
          </div>
          <span className="font-mono text-[10px] tabular-nums opacity-70">1:12</span>
        </div>
      </div>
    );
  }

  // file (log)
  return (
    <div className="aspect-[16/9] w-full relative overflow-hidden bg-zinc-950">
      <div className="absolute inset-0 p-3 pt-8 font-mono text-[9.5px] leading-[1.55] text-zinc-300 overflow-hidden">
        <div className="text-zinc-500">[11:00:14.221] <span className="text-blue-400">INFO</span>  wallet.transfer received id=tx_aGc1z amount=42.00</div>
        <div className="text-zinc-500">[11:00:14.224] <span className="text-blue-400">INFO</span>  wallet.transfer received id=tx_aGc1z amount=42.00 <span className="text-amber-400">// duplicate within 200ms</span></div>
        <div className="text-zinc-500">[11:00:14.238] <span className="text-blue-400">DEBUG</span> lock.acquire row=wallet:u_3142 ok</div>
        <div className="text-zinc-500">[11:00:14.239] <span className="text-blue-400">DEBUG</span> lock.acquire row=wallet:u_3142 <span className="text-red-400">MISS</span> — no pessimistic lock</div>
        <div className="text-zinc-500">[11:00:14.301] <span className="text-red-400">ERROR</span> balance_inconsistent debit_count=2 trace=wlt-7f4-aGc1z</div>
        <div className="text-zinc-500">[11:00:14.305] <span className="text-red-400">ERROR</span>   at wallet.svc.transfer (transfer.ts:142)</div>
        <div className="text-zinc-600">[11:00:14.401] <span className="text-blue-400">INFO</span>  500 returned to client in 187ms</div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-zinc-950 to-transparent" />
    </div>
  );
}

function TriageScreen({ openIssue }) {
  const { issues, updateIssue } = useApp();
  const toast = useToast();
  const queue = useMemo(() => issues.filter(i => !i.assignee), [issues]);
  const [selectedId, setSelectedId] = useState(queue[0]?.id);
  const selected = issues.find(i => i.id === selectedId);

  const [assignee, setAssignee] = useState(null);
  const [severity, setSeverity] = useState(selected?.severity || 'major');
  const [labels, setLabels] = useState([]);
  const [blocker, setBlocker] = useState(false);

  useEffect(() => {
    if (selected) {
      setSeverity(selected.severity);
      setLabels(selected.labels);
      setBlocker(selected.releaseBlocker);
      setAssignee(null);
    }
  }, [selected?.id]);

  if (!selected) return <Empty icon="check-check" title="Triage zero" body="No unassigned issues right now." />;

  const triage = () => {
    if (!assignee) return;
    updateIssue({ ...selected, assignee, severity, releaseBlocker: blocker, status: 'triaged' });
    const u = userById(assignee);
    toast({ title: `${selected.id} assigned to ${u.name}`, body: `Severity set to ${SEVERITY[severity].label}`, target: u.tg, warn: !u.tgConnected });
    setTimeout(() => {
      const next = queue.find(q => q.id !== selected.id);
      if (next) setSelectedId(next.id);
    }, 200);
  };

  return (
    <div className="grid grid-cols-[1fr_440px] h-full min-h-0">
      <div className="border-r border-zinc-200 dark:border-zinc-800 overflow-y-auto">
        <div className="px-7 py-4 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-white/95 dark:bg-zinc-950/95 backdrop-blur z-10">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Triage queue</h1>
          <p className="text-[12px] text-zinc-500 dark:text-zinc-400">{queue.length} unassigned · sorted by severity &amp; age</p>
        </div>
        <ul>
          {queue.map(i => {
            const r = userById(i.reporter);
            const hours = i.age.endsWith('h') ? parseFloat(i.age) : parseFloat(i.age) * 24;
            const sla = slaColor(hours);
            return (
              <li key={i.id}>
                <button onClick={() => setSelectedId(i.id)}
                  className={cn('w-full text-left px-7 py-3 border-b border-zinc-100 dark:border-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-900/40 transition-colors',
                    selectedId === i.id && 'bg-zinc-100/70 dark:bg-zinc-800/60')}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <SeverityBadge value={i.severity} dot />
                    <span className="font-mono text-[11px] text-zinc-500">{i.id}</span>
                    <span className="ml-auto inline-flex items-center gap-1 text-[11px]">
                      <span className={cn('h-1.5 w-1.5 rounded-full', sla.dot)} />
                      <span className={sla.text}>filed {i.age} ago</span>
                    </span>
                  </div>
                  <div className="text-[13.5px] font-medium text-zinc-900 dark:text-zinc-100 leading-snug">{i.title}</div>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-zinc-500">
                    <Avatar user={r} size={14} />
                    <span>{r?.name}</span>
                    <RoleBadge value={i.reporterRole} />
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="overflow-y-auto bg-zinc-50/60 dark:bg-zinc-900/40">
        <div className="px-5 py-5">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-[12px] text-zinc-500">{selected.id}</span>
            <SeverityBadge value={selected.severity} dot />
            <StatusBadge value={selected.status} />
          </div>
          <h2 className="text-[17px] font-semibold leading-snug text-zinc-900 dark:text-zinc-100">{selected.title}</h2>

          <div className="mt-3 text-[13px] text-zinc-700 dark:text-zinc-200 leading-relaxed">
            Two simultaneous requests within ~200ms cause the second to read stale state and double-debit.
            Confirmed on <code className="font-mono text-[12px] bg-zinc-100 dark:bg-zinc-800 px-1 rounded">staging-2</code>.
            <button className="ml-1 text-[11.5px] text-blue-600 dark:text-blue-400">expand</button>
          </div>

          <TriageMediaPreview />


          <div className="mt-5">
            <div className="text-[10.5px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400 mb-1.5">Severity</div>
            <div className="grid grid-cols-5 gap-1">
              {Object.keys(SEVERITY).map(s => (
                <button key={s} onClick={() => setSeverity(s)}
                  className={cn('h-8 rounded-md text-[11.5px] font-medium border transition-colors',
                    severity === s
                      ? 'bg-zinc-900 text-white border-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 dark:border-zinc-100'
                      : 'bg-white text-zinc-700 border-zinc-200 hover:bg-zinc-50 dark:bg-zinc-950 dark:text-zinc-300 dark:border-zinc-800 dark:hover:bg-zinc-900')}>{SEVERITY[s].label}</button>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <div className="text-[10.5px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400 mb-1.5">Assign to</div>
            <div className="grid grid-cols-1 gap-1.5">
              {MOCK_TEAM.filter(u => u.role === 'developer').map(u => (
                <button key={u.id} onClick={() => setAssignee(u.id)}
                  className={cn('flex items-center gap-2 px-2.5 h-9 rounded-md border text-[12.5px] transition-colors',
                    assignee === u.id
                      ? 'border-zinc-900 bg-zinc-50 dark:border-zinc-100 dark:bg-zinc-800'
                      : 'border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-900')}>
                  <Avatar user={u} size={22} />
                  <span className="font-medium text-zinc-900 dark:text-zinc-100">{u.name}</span>
                  <span className="text-[10.5px] text-zinc-500 font-mono ml-1">{u.tg}</span>
                  {!u.tgConnected
                    ? <span className="ml-auto text-[10px] text-amber-600 inline-flex items-center gap-0.5"><Icon name="triangle-alert" size={9} /> not connected</span>
                    : <span className="ml-auto text-[10px] text-emerald-600 inline-flex items-center gap-0.5"><Icon name="check" size={9} /> reachable</span>}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <div className="text-[10.5px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400 mb-1.5">Labels</div>
              <div className="flex flex-wrap gap-1">
                {['wallet','payments','auth','api','ui','reports'].map(l => (
                  <button key={l} onClick={() => setLabels(L => L.includes(l) ? L.filter(x => x !== l) : [...L, l])}
                    className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[11px]',
                      labels.includes(l)
                        ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                        : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700')}>{l}</button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400 mb-1.5">Release blocker</div>
              <button onClick={() => setBlocker(b => !b)}
                className={cn('flex items-center justify-between w-full h-9 px-3 rounded-md border',
                  blocker ? 'bg-red-50 border-red-200 dark:bg-red-950/40 dark:border-red-900' : 'border-zinc-200 dark:border-zinc-800')}>
                <span className={cn('text-[12.5px] font-medium', blocker ? 'text-red-700 dark:text-red-300' : 'text-zinc-700 dark:text-zinc-200')}>
                  {blocker ? 'Blocks v2.4.1' : 'Not a blocker'}
                </span>
                <Switch checked={blocker} onChange={setBlocker} />
              </button>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-2">
            <Button onClick={triage} disabled={!assignee} className="flex-1">
              <Icon name="send" size={13} /> Assign &amp; triage
            </Button>
            <Button variant="outline" className="flex-1" onClick={() => openIssue(selected)}>
              <Icon name="message-circle" size={13} /> Needs clarification
            </Button>
          </div>
          {assignee && (
            <div className="mt-2 text-[11px] text-zinc-500 inline-flex items-center gap-1">
              <Icon name="send" size={11} className="text-blue-500" /> Will Telegram-ping {userById(assignee).tg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  DashboardScreen, IssuesScreen, TriageScreen,
  IssueTable, IssueBoard, FilterDropdown, FilterChipStatic,
  DashStat,
});
