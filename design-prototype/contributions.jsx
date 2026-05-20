// ─── Contributions report ───────────────────────────────────────────────────

const Recharts = window.Recharts;

function ContributionsScreen({ openIssue }) {
  const [roleFilter, setRoleFilter] = useState('all');
  const [stacked, setStacked] = useState(false);
  const [drilldown, setDrilldown] = useState(null);

  const rows = useMemo(() => {
    return MOCK_CONTRIBUTIONS
      .map(c => ({ ...c, user: userById(c.memberId) }))
      .filter(r => roleFilter === 'all' || r.user.role === roleFilter);
  }, [roleFilter]);

  const topReporter = [...rows].sort((a,b) => b.reported - a.reported)[0];
  const topSolver   = [...rows].sort((a,b) => b.fixed - a.fixed)[0];

  // Chart data
  const chartData = rows.map(r => ({
    name: r.user.name.replace('.',''),
    reported: r.reported,
    fixed: r.fixed,
    blocker: r.repBySev.blocker,
    critical: r.repBySev.critical,
    major: r.repBySev.major,
    minor: r.repBySev.minor,
    enhancement: r.repBySev.enhancement,
  }));

  return (
    <div className="px-7 py-6">
      {/* Header */}
      <div className="flex items-end justify-between mb-5">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Reports</div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">Contributions</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Who's filing what, who's fixing what, and how long it takes — for the current release.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm"><Icon name="download" size={12} /> Export CSV</Button>
          <Button variant="outline" size="sm"><Icon name="share-2" size={12} /> Share</Button>
        </div>
      </div>

      {/* Filter bar */}
      <Card className="px-4 py-3 mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <FilterChip icon="tag" label="Release" value="v2.4.1" />
          <FilterChip icon="calendar" label="Date" value="May 12 – May 20, 2025" />
          <FilterChip icon="folder" label="Project" value="Core API" />
          <div className="ml-auto">
            <Segmented
              size="sm"
              value={roleFilter}
              onChange={setRoleFilter}
              options={[
                { value: 'all', label: 'All roles' },
                { value: 'qa', label: 'QA' },
                { value: 'developer', label: 'Devs' },
                { value: 'cto', label: 'CTO' },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <MemberMetricCard title="Most active reporter" user={topReporter.user} value={`${topReporter.reported} issues`} />
        <MemberMetricCard title="Top solver" user={topSolver.user} value={`${topSolver.fixed} fixed`} />
        <MetricCard label="Avg time to fix (Blocker)" value="4.2h"  tone="red"   sub="median 3.8h · fastest 1.1h" icon="zap" />
        <MetricCard label="Avg time to fix (Critical)" value="18.6h" tone="amber" sub="median 16h · slowest 72h" icon="zap" />
      </div>

      {/* Overview chart */}
      <Card className="mb-4">
        <div className="px-5 pt-4 flex items-center justify-between">
          <div>
            <CardTitle>Contribution overview</CardTitle>
            <CardDesc>Issues reported vs fixed per person</CardDesc>
          </div>
          <Segmented
            size="sm"
            value={stacked ? 'stacked' : 'simple'}
            onChange={(v) => setStacked(v === 'stacked')}
            options={[
              { value: 'simple', label: 'Reported / fixed' },
              { value: 'stacked', label: 'By severity' },
            ]}
          />
        </div>
        <div className="px-2 pb-3 pt-3" style={{ height: 280 }}>
          <Recharts.ResponsiveContainer width="100%" height="100%">
            <Recharts.BarChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <Recharts.CartesianGrid stroke="rgba(150,150,150,0.15)" vertical={false} />
              <Recharts.XAxis dataKey="name" tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
              <Recharts.YAxis tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
              <Recharts.Tooltip
                cursor={{ fill: 'rgba(150,150,150,0.08)' }}
                contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e4e4e7', boxShadow: '0 4px 12px rgba(0,0,0,0.06)' }}
              />
              <Recharts.Legend wrapperStyle={{ fontSize: 11 }} />
              {stacked ? (
                <>
                  <Recharts.Bar dataKey="blocker" stackId="rep" fill="#ef4444" radius={[0,0,0,0]} />
                  <Recharts.Bar dataKey="critical" stackId="rep" fill="#f97316" />
                  <Recharts.Bar dataKey="major" stackId="rep" fill="#f59e0b" />
                  <Recharts.Bar dataKey="minor" stackId="rep" fill="#3b82f6" radius={[3,3,0,0]} />
                </>
              ) : (
                <>
                  <Recharts.Bar dataKey="reported" fill="#3b82f6" radius={[4,4,0,0]} />
                  <Recharts.Bar dataKey="fixed" fill="#10b981" radius={[4,4,0,0]} />
                </>
              )}
            </Recharts.BarChart>
          </Recharts.ResponsiveContainer>
        </div>
      </Card>

      {/* Two tables side by side */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <Card>
          <CardHeader>
            <CardTitle>Bug reporters</CardTitle>
            <CardDesc>Ranked by total issues filed in v2.4.1</CardDesc>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                <tr>
                  <th className="text-left font-medium px-4 py-2">#</th>
                  <th className="text-left font-medium px-2 py-2">Member</th>
                  <th className="text-right font-medium px-2 py-2">Reported</th>
                  <th className="text-right font-medium px-2 py-2">Blk</th>
                  <th className="text-right font-medium px-2 py-2">Crit</th>
                  <th className="text-right font-medium px-2 py-2">Maj</th>
                  <th className="text-right font-medium px-2 py-2">Min</th>
                  <th className="text-right font-medium px-4 py-2">Regr.</th>
                </tr>
              </thead>
              <tbody>
                {[...rows].sort((a,b) => b.reported - a.reported).map((r, i) => (
                  <tr key={r.memberId}
                    onClick={() => setDrilldown(r)}
                    className="border-b border-zinc-100 dark:border-zinc-900 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-900/40 cursor-pointer">
                    <td className="px-4 py-2 text-zinc-400 font-mono text-[11px]">{i + 1}</td>
                    <td className="px-2 py-2">
                      <div className="flex items-center gap-2">
                        <Avatar user={r.user} size={22} />
                        <span className="font-medium text-zinc-900 dark:text-zinc-100">{r.user.name}</span>
                        <RoleBadge value={r.user.role} />
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right font-semibold tabular-nums">{r.reported}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-zinc-500"><SevCount n={r.repBySev.blocker} sev="blocker" /></td>
                    <td className="px-2 py-2 text-right tabular-nums text-zinc-500"><SevCount n={r.repBySev.critical} sev="critical" /></td>
                    <td className="px-2 py-2 text-right tabular-nums text-zinc-500"><SevCount n={r.repBySev.major} sev="major" /></td>
                    <td className="px-2 py-2 text-right tabular-nums text-zinc-500"><SevCount n={r.repBySev.minor} sev="minor" /></td>
                    <td className="px-4 py-2 text-right tabular-nums text-zinc-500">{r.repBySev.blocker + r.repBySev.critical}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Issue solvers</CardTitle>
            <CardDesc>Ranked by total fixes in v2.4.1</CardDesc>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                <tr>
                  <th className="text-left font-medium px-4 py-2">#</th>
                  <th className="text-left font-medium px-2 py-2">Member</th>
                  <th className="text-right font-medium px-2 py-2">Fixed</th>
                  <th className="text-right font-medium px-2 py-2">Avg TTF</th>
                  <th className="text-right font-medium px-2 py-2">Regr. caused</th>
                  <th className="text-left  font-medium px-4 py-2">Fix rate</th>
                </tr>
              </thead>
              <tbody>
                {[...rows].sort((a,b) => b.fixed - a.fixed).map((r, i) => (
                  <tr key={r.memberId}
                    onClick={() => setDrilldown(r)}
                    className="border-b border-zinc-100 dark:border-zinc-900 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-900/40 cursor-pointer">
                    <td className="px-4 py-2 text-zinc-400 font-mono text-[11px]">{i + 1}</td>
                    <td className="px-2 py-2">
                      <div className="flex items-center gap-2">
                        <Avatar user={r.user} size={22} />
                        <span className="font-medium text-zinc-900 dark:text-zinc-100">{r.user.name}</span>
                        <RoleBadge value={r.user.role} />
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right font-semibold tabular-nums">{r.fixed}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-zinc-600 dark:text-zinc-400">{r.avgFixH ? r.avgFixH + 'h' : '—'}</td>
                    <td className={cn('px-2 py-2 text-right tabular-nums', r.regressionsCaused > 0 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-zinc-500')}>
                      {r.regressionsCaused || '—'}
                    </td>
                    <td className="px-4 py-2">
                      {r.fixRate != null ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                            <div className={cn('h-full rounded-full',
                              r.fixRate >= 95 ? 'bg-emerald-500' : r.fixRate >= 85 ? 'bg-amber-500' : 'bg-red-500')}
                              style={{ width: `${r.fixRate}%` }} />
                          </div>
                          <span className="text-[11px] text-zinc-500 tabular-nums">{r.fixRate}%</span>
                        </div>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Time-to-fix */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Time-to-fix metrics</CardTitle>
          <CardDesc>Distribution of fix duration by severity, across the current release</CardDesc>
        </CardHeader>
        <div className="grid grid-cols-[1fr_2fr] gap-0 px-2 pb-3">
          <div>
            <table className="w-full text-[12.5px]">
              <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                <tr>
                  <th className="text-left font-medium px-3 py-2">Severity</th>
                  <th className="text-right font-medium px-2 py-2">Avg</th>
                  <th className="text-right font-medium px-2 py-2">Median</th>
                  <th className="text-right font-medium px-2 py-2">Fastest</th>
                  <th className="text-right font-medium px-3 py-2">Slowest</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_TIME_TO_FIX.map(r => (
                  <tr key={r.severity} className="border-b border-zinc-100 dark:border-zinc-900 last:border-0">
                    <td className="px-3 py-2"><SeverityBadge value={r.severity} dot size="sm" /></td>
                    <td className="px-2 py-2 text-right font-semibold tabular-nums">{fmtH(r.avgH)}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-zinc-600 dark:text-zinc-400">{fmtH(r.medianH)}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-emerald-600 dark:text-emerald-400">{fmtH(r.fastestH)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-600 dark:text-red-400">{fmtH(r.slowestH)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="border-l border-zinc-200 dark:border-zinc-800 pl-2" style={{ height: 280 }}>
            <Recharts.ResponsiveContainer width="100%" height="100%">
              <Recharts.ScatterChart margin={{ top: 10, right: 24, bottom: 24, left: 24 }}>
                <Recharts.CartesianGrid stroke="rgba(150,150,150,0.15)" />
                <Recharts.XAxis
                  dataKey="hours"
                  name="hours"
                  type="number"
                  scale="log"
                  domain={[1, 500]}
                  ticks={[1, 4, 16, 48, 168, 500]}
                  tick={{ fontSize: 11, fill: '#71717a' }}
                  axisLine={false}
                  tickLine={false}
                  label={{ value: 'hours to fix (log)', position: 'insideBottom', offset: -10, style: { fill: '#71717a', fontSize: 11 } }}
                />
                <Recharts.YAxis
                  dataKey="sevIdx"
                  type="number"
                  domain={[-0.5, 4.5]}
                  ticks={[0,1,2,3,4]}
                  tickFormatter={(v) => ['Enh', 'Minor', 'Major', 'Crit', 'Blk'][v]}
                  tick={{ fontSize: 11, fill: '#71717a' }}
                  axisLine={false}
                  tickLine={false}
                  width={50}
                />
                <Recharts.Tooltip
                  cursor={{ stroke: 'rgba(0,0,0,0.1)' }}
                  contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e4e4e7' }}
                  formatter={(value, name, props) => {
                    if (name === 'hours') return [value + 'h', 'Time to fix'];
                    return [value, name];
                  }}
                  labelFormatter={() => ''}
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null;
                    const p = payload[0].payload;
                    return (
                      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3 py-2 text-[12px] shadow-md">
                        <div className="font-mono text-[11px] text-zinc-500">{p.id}</div>
                        <div className="font-medium">{fmtH(p.hours)} to fix</div>
                        <div className="text-zinc-500 mt-0.5">by {p.fixer}</div>
                      </div>
                    );
                  }}
                />
                <Recharts.Scatter data={MOCK_FIX_SCATTER}>
                  {MOCK_FIX_SCATTER.map((d, i) => (
                    <Recharts.Cell key={i} fill={
                      d.sev === 'blocker' ? '#ef4444' :
                      d.sev === 'critical' ? '#f97316' :
                      d.sev === 'major' ? '#f59e0b' :
                      d.sev === 'minor' ? '#3b82f6' : '#a1a1aa'
                    } />
                  ))}
                </Recharts.Scatter>
              </Recharts.ScatterChart>
            </Recharts.ResponsiveContainer>
          </div>
        </div>
      </Card>

      {/* Drilldown panel */}
      {drilldown && (
        <Dialog open={!!drilldown} onClose={() => setDrilldown(null)} width={720}>
          <ContributionDrilldown row={drilldown} onClose={() => setDrilldown(null)} openIssue={openIssue} />
        </Dialog>
      )}
    </div>
  );
}

function fmtH(h) {
  if (h == null) return '—';
  if (h >= 48) return (h / 24).toFixed(1) + 'd';
  return h + 'h';
}

function FilterChip({ icon, label, value }) {
  return (
    <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 hover:bg-zinc-50 dark:hover:bg-zinc-900 text-[12px]">
      <Icon name={icon} size={12} className="text-zinc-500" />
      <span className="text-zinc-500">{label}</span>
      <span className="font-medium text-zinc-800 dark:text-zinc-100">{value}</span>
      <Icon name="chevron-down" size={11} className="text-zinc-400" />
    </button>
  );
}

function MemberMetricCard({ title, user, value }) {
  return (
    <Card className="p-4">
      <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{title}</div>
      <div className="mt-2 flex items-center gap-3">
        <Avatar user={user} size={42} />
        <div className="min-w-0">
          <div className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-100 leading-tight">{user?.name}</div>
          <div className="flex items-center gap-1.5 mt-1">
            <RoleBadge value={user?.role} />
            <span className="text-[12px] text-zinc-500">{value}</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function SevCount({ n, sev }) {
  if (!n) return <span className="text-zinc-300">·</span>;
  return (
    <span className="inline-flex items-center gap-1 text-zinc-700 dark:text-zinc-200 font-medium">
      <span className={cn('h-1.5 w-1.5 rounded-full', SEVERITY[sev].dot)} />
      {n}
    </span>
  );
}

function ContributionDrilldown({ row, onClose, openIssue }) {
  // simulate per-member issue lists
  const reported = MOCK_ISSUES.filter(i => i.reporter === row.memberId).slice(0, 5);
  const fixed = MOCK_ISSUES.filter(i => i.assignee === row.memberId && (i.status === 'fixed' || i.status === 'verified')).slice(0, 5);
  const daySeries = [
    { day: 'Mon', filed: row.reported >= 5 ? 3 : 1, fixed: row.fixed >= 5 ? 1 : 0 },
    { day: 'Tue', filed: row.reported >= 5 ? 2 : 1, fixed: row.fixed >= 5 ? 2 : 0 },
    { day: 'Wed', filed: row.reported >= 5 ? 4 : 1, fixed: row.fixed >= 5 ? 1 : 0 },
    { day: 'Thu', filed: row.reported >= 5 ? 2 : 0, fixed: row.fixed >= 5 ? 3 : 1 },
    { day: 'Fri', filed: row.reported >= 5 ? 2 : 1, fixed: row.fixed >= 5 ? 2 : 1 },
    { day: 'Sat', filed: 1, fixed: row.fixed >= 5 ? 1 : 0 },
    { day: 'Sun', filed: 0, fixed: row.fixed >= 5 ? 1 : 0 },
  ];

  return (
    <>
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <Avatar user={row.user} size={36} />
          <div>
            <div className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{row.user.name}</div>
            <div className="flex items-center gap-2 text-[12px] text-zinc-500 mt-0.5">
              <RoleBadge value={row.user.role} />
              <span>{row.user.tg}</span>
              {!row.user.tgConnected && <span className="text-amber-600">· Telegram not connected</span>}
            </div>
          </div>
        </div>
        <button onClick={onClose} className="h-8 w-8 rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center">
          <Icon name="x" size={16} />
        </button>
      </div>

      <div className="overflow-y-auto px-5 py-4">
        {/* Mini stats */}
        <div className="grid grid-cols-4 gap-3 mb-5">
          <MiniStat label="Reported" value={row.reported} tone="blue" />
          <MiniStat label="Fixed" value={row.fixed} tone="green" />
          <MiniStat label="Avg TTF" value={row.avgFixH ? row.avgFixH + 'h' : '—'} />
          <MiniStat label="Fix rate" value={row.fixRate ? row.fixRate + '%' : '—'} />
        </div>

        {/* Activity chart */}
        <div className="mb-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-2">Activity this release</div>
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-2" style={{ height: 160 }}>
            <Recharts.ResponsiveContainer width="100%" height="100%">
              <Recharts.LineChart data={daySeries} margin={{ top: 6, right: 8, bottom: 0, left: -16 }}>
                <Recharts.CartesianGrid stroke="rgba(150,150,150,0.15)" vertical={false} />
                <Recharts.XAxis dataKey="day" tick={{ fontSize: 10, fill: '#71717a' }} axisLine={false} tickLine={false} />
                <Recharts.YAxis tick={{ fontSize: 10, fill: '#71717a' }} axisLine={false} tickLine={false} />
                <Recharts.Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e4e4e7' }} />
                <Recharts.Line type="monotone" dataKey="filed" stroke="#3b82f6" strokeWidth={2} dot={{ r: 2 }} />
                <Recharts.Line type="monotone" dataKey="fixed" stroke="#10b981" strokeWidth={2} dot={{ r: 2 }} />
              </Recharts.LineChart>
            </Recharts.ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-2">Reported</div>
            <div className="space-y-1">
              {reported.length === 0 ? <div className="text-[12px] text-zinc-400">No issues reported</div>
              : reported.map(i => <DrillIssueRow key={i.id} issue={i} onClick={() => openIssue(i)} />)}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-2">Fixed</div>
            <div className="space-y-1">
              {fixed.length === 0 ? <div className="text-[12px] text-zinc-400">No fixes yet</div>
              : fixed.map(i => <DrillIssueRow key={i.id} issue={i} ttf onClick={() => openIssue(i)} />)}
            </div>
          </div>
        </div>

        {row.regressionsCaused > 0 && (
          <div className="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 text-[12.5px] text-amber-800 dark:text-amber-200 leading-snug">
            <strong className="font-semibold">{row.regressionsCaused} issue{row.regressionsCaused === 1 ? '' : 's'}</strong> that {row.user.name} fixed later regressed.
            These may benefit from a more robust fix or test coverage — not a reflection on the engineer.
          </div>
        )}
      </div>
    </>
  );
}

function MiniStat({ label, value, tone }) {
  const tones = { blue: 'text-blue-600 dark:text-blue-400', green: 'text-emerald-600 dark:text-emerald-400' };
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 px-3 py-2">
      <div className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className={cn('text-[16px] font-semibold tabular-nums', tones[tone] || 'text-zinc-900 dark:text-zinc-100')}>{value}</div>
    </div>
  );
}

function DrillIssueRow({ issue, ttf, onClick }) {
  return (
    <button onClick={onClick} className="w-full flex items-center gap-2 text-left rounded-md hover:bg-zinc-50 dark:hover:bg-zinc-900 px-2 py-1.5">
      <SeverityBadge value={issue.severity} size="sm" />
      <span className="font-mono text-[11px] text-zinc-500">{issue.id}</span>
      <span className="text-[13px] text-zinc-800 dark:text-zinc-100 truncate flex-1">{issue.title}</span>
      {ttf && issue.timeToFixH != null && (
        <span className="text-[11px] text-zinc-500 tabular-nums">{issue.timeToFixH}h</span>
      )}
    </button>
  );
}

Object.assign(window, { ContributionsScreen });
