// ─── Screens part B: Regressions, Releases, Reports, Settings, NewIssue ────

const _RB = window.Recharts;

// ─────────────────────────────────────────────────────────────────────────
//  REGRESSIONS
// ─────────────────────────────────────────────────────────────────────────
function RegressionsScreen({ openIssue }) {
  return (
    <div className="px-7 py-6">
      <div className="mb-5">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Quality</div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">Regressions</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Bugs that keep coming back and the components they live in.</p>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        <MetricCard label="Regression rate"    value="23%" tone="amber" sub="of closed bugs returned" icon="refresh-ccw" />
        <MetricCard label="Total regressions"  value="11"  tone="red"   sub="last 4 releases"        icon="alert-triangle" />
        <Card className="p-4">
          <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Most regressed</div>
          <div className="mt-2 text-[13px] font-semibold text-zinc-900 dark:text-zinc-100 leading-snug">Wallet sync fails on concurrent transactions</div>
          <div className="mt-2 inline-flex items-center gap-1 text-red-600 dark:text-red-400 text-[12px] font-medium">
            <Icon name="refresh-ccw" size={12} /> Regressed 3×
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Most fragile component</div>
          <div className="mt-2 flex items-center gap-2">
            <LabelChip>wallet</LabelChip>
            <span className="text-[12px] text-zinc-500">5 distinct regressions</span>
          </div>
          <div className="mt-3 h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full">
            <div className="h-full bg-red-500 rounded-full" style={{ width: '90%' }} />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-[1fr_380px] gap-4">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Recurrence timeline</CardTitle>
            <CardDesc>How top recurring issues behaved across the last six releases</CardDesc>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
                <tr>
                  <th className="text-left font-medium px-4 py-2 min-w-[280px]">Issue</th>
                  {['v2.1', 'v2.2', 'v2.3', 'v2.4', 'v2.4.1', 'v2.5'].map(v => <th key={v} className="text-center font-medium px-2 py-2 font-mono">{v}</th>)}
                </tr>
              </thead>
              <tbody>
                {MOCK_RECURRING.map(r => {
                  const issue = MOCK_ISSUES.find(i => i.id === r.id);
                  return (
                    <tr key={r.id} className="border-b border-zinc-100 dark:border-zinc-900 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-900/40 cursor-pointer" onClick={() => issue && openIssue(issue)}>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[11px] text-zinc-500">{r.id}</span>
                          <LabelChip>{r.component}</LabelChip>
                        </div>
                        <div className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 mt-0.5">{r.title}</div>
                      </td>
                      {r.history.map(h => (
                        <td key={h.v} className="text-center px-2 py-2.5">
                          <span className={cn('inline-flex h-6 w-6 rounded-full items-center justify-center',
                            h.s === 'fixed' && 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
                            h.s === 'regression' && 'bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300',
                            h.s === 'open' && 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300',
                            h.s === 'in-progress' && 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300',
                            h.s === '—' && 'text-zinc-300')}>
                            <Icon name={h.s === 'fixed' ? 'check'
                                       : h.s === 'regression' ? 'refresh-ccw'
                                       : h.s === 'open' ? 'circle-dot'
                                       : h.s === 'in-progress' ? 'loader-circle'
                                       : 'minus'} size={11} />
                          </span>
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Component fragility</CardTitle>
            <CardDesc>Total regressions, last 4 releases</CardDesc>
          </CardHeader>
          <CardBody className="pt-0">
            <ul className="space-y-2.5">
              {MOCK_FRAGILE.map(f => {
                const pct = (f.count / 5) * 100;
                const tone = f.count > 4 ? 'red' : f.count > 2 ? 'amber' : 'emerald';
                return (
                  <li key={f.component}>
                    <div className="flex items-center justify-between text-[12.5px] mb-1">
                      <LabelChip>{f.component}</LabelChip>
                      <span className={cn('font-semibold tabular-nums',
                        tone === 'red' && 'text-red-600 dark:text-red-400',
                        tone === 'amber' && 'text-amber-600 dark:text-amber-400',
                        tone === 'emerald' && 'text-emerald-600 dark:text-emerald-400')}>{f.count}</span>
                    </div>
                    <div className="h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                      <div className={cn('h-full rounded-full',
                        tone === 'red' && 'bg-red-500',
                        tone === 'amber' && 'bg-amber-500',
                        tone === 'emerald' && 'bg-emerald-500')} style={{ width: pct + '%' }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardBody>
        </Card>
      </div>

      <div className="mt-4 p-4 rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900/50 flex items-start gap-3">
        <div className="h-9 w-9 rounded-lg bg-amber-100 dark:bg-amber-900/60 flex items-center justify-center text-amber-700 dark:text-amber-300 shrink-0">
          <Icon name="lightbulb" size={15} />
        </div>
        <div className="text-[13px] flex-1">
          <div className="font-semibold text-amber-900 dark:text-amber-200">Suggested action</div>
          <div className="text-amber-800 dark:text-amber-300 mt-0.5 leading-relaxed">
            Payments and Wallet have a <strong>combined regression rate of 45%</strong>. Adding integration test
            coverage for concurrent transfers and gateway retries would catch the top two recurring issues before release.
          </div>
        </div>
        <Button variant="outline" size="sm">Suggest test coverage <Icon name="arrow-up-right" size={11} /></Button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  RELEASES list + detail
// ─────────────────────────────────────────────────────────────────────────
function ReleasesScreen({ openIssue }) {
  const [selectedId, setSelectedId] = useState('r1');
  const release = MOCK_RELEASES.find(r => r.id === selectedId);
  const proj = MOCK_PROJECTS.find(p => p.id === release.projectId);
  const releaseIssues = MOCK_ISSUES.filter(i => i.release === release.version);

  const breakdown = useMemo(() => {
    const counts = {};
    releaseIssues.forEach(i => { counts[i.severity] = (counts[i.severity] || 0) + 1; });
    return Object.entries(counts).map(([sev, value]) => ({ name: SEVERITY[sev].label, value, sev }));
  }, [releaseIssues]);

  return (
    <div className="grid grid-cols-[360px_1fr] h-full min-h-0">
      <div className="border-r border-zinc-200 dark:border-zinc-800 overflow-y-auto">
        <div className="px-5 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Releases</h1>
          <Button size="sm" variant="outline"><Icon name="plus" size={12} /> New</Button>
        </div>
        <ul>
          {MOCK_RELEASES.map(r => {
            const p = MOCK_PROJECTS.find(pp => pp.id === r.projectId);
            const tone = r.blockers > 0 ? 'red' : r.criticals > 0 ? 'amber' : r.signedOff ? 'green' : 'blue';
            return (
              <li key={r.id}>
                <button onClick={() => setSelectedId(r.id)}
                  className={cn('w-full text-left px-5 py-3 border-b border-zinc-100 dark:border-zinc-900',
                    selectedId === r.id ? 'bg-zinc-100/70 dark:bg-zinc-800/60' : 'hover:bg-zinc-50 dark:hover:bg-zinc-900/40')}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100">{r.version}</span>
                    <Badge tone={tone}>{r.signedOff ? 'Signed off' : r.status}</Badge>
                  </div>
                  <div className="text-[12px] text-zinc-500">{p.name}</div>
                  <div className="mt-1.5 flex items-center gap-3 text-[11px] text-zinc-500">
                    <span><span className="text-red-600 dark:text-red-400 font-semibold">{r.blockers}</span> blk</span>
                    <span><span className="text-amber-600 dark:text-amber-400 font-semibold">{r.criticals}</span> crit</span>
                    <span><span className="text-emerald-600 dark:text-emerald-400 font-semibold">{r.fixed}</span>/{r.total} fixed</span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="overflow-y-auto">
        <div className="px-7 py-5 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 text-[12px] text-zinc-500">
                <span>{proj.name}</span>
                <Icon name="chevron-right" size={12} className="text-zinc-300" />
                <Badge tone={release.status === 'active' ? 'blue' : 'muted'}>{release.status}</Badge>
              </div>
              <h2 className="text-2xl font-semibold font-mono text-zinc-900 dark:text-zinc-100 mt-1">{release.version}</h2>
              <div className="text-[12.5px] text-zinc-500 mt-1">Released window: May 12 – May 22, 2025 · last activity {release.lastActivity}</div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm"><Icon name="download" size={12} /> Export report</Button>
              <Button variant={release.blockers > 0 ? 'destructive' : 'success'} disabled={release.blockers > 0 && release.signedOff}>
                {release.blockers > 0 ? <><Icon name="octagon-alert" size={13} /> {release.blockers} blocker{release.blockers === 1 ? '' : 's'} · No-Go</>
                : release.signedOff ? <><Icon name="check" size={13} /> Approved</>
                : <><Icon name="check" size={13} /> Approve release</>}
              </Button>
            </div>
          </div>
        </div>

        <div className="px-7 py-5">
          <div className="grid grid-cols-5 gap-3 mb-4">
            <MetricCard label="Filed"     value={release.total}              icon="file-plus" />
            <MetricCard label="Fixed"     value={release.fixed}    tone="green" icon="check" />
            <MetricCard label="Verified"  value={Math.floor(release.fixed * 0.6)} tone="green" icon="shield-check" />
            <MetricCard label="Blockers"  value={release.blockers} tone={release.blockers ? 'red' : 'default'} icon="octagon-alert" />
            <MetricCard label="Regression rate" value={release.regressionRate + '%'} tone="amber" icon="refresh-ccw" />
          </div>

          <div className="grid grid-cols-[1fr_1fr] gap-4">
            <Card>
              <CardHeader><CardTitle>Severity breakdown</CardTitle></CardHeader>
              <div className="px-2 pb-4" style={{ height: 260 }}>
                <_RB.ResponsiveContainer width="100%" height="100%">
                  <_RB.PieChart>
                    <_RB.Pie data={breakdown} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={2}>
                      {breakdown.map(b => (
                        <_RB.Cell key={b.sev} fill={
                          b.sev === 'blocker' ? '#ef4444' :
                          b.sev === 'critical' ? '#f97316' :
                          b.sev === 'major' ? '#f59e0b' :
                          b.sev === 'minor' ? '#3b82f6' : '#a1a1aa'
                        } />
                      ))}
                    </_RB.Pie>
                    <_RB.Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e4e4e7' }} />
                    <_RB.Legend wrapperStyle={{ fontSize: 11 }} verticalAlign="bottom" iconType="circle" />
                  </_RB.PieChart>
                </_RB.ResponsiveContainer>
              </div>
            </Card>

            <Card>
              <CardHeader><CardTitle>Bug discovery</CardTitle><CardDesc>Filed vs fixed per day</CardDesc></CardHeader>
              <div className="px-2 pb-4" style={{ height: 260 }}>
                <_RB.ResponsiveContainer width="100%" height="100%">
                  <_RB.LineChart data={MOCK_DISCOVERY} margin={{ top: 6, right: 18, bottom: 6, left: -10 }}>
                    <_RB.CartesianGrid stroke="rgba(150,150,150,0.15)" vertical={false} />
                    <_RB.XAxis dataKey="day" tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
                    <_RB.YAxis tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
                    <_RB.Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e4e4e7' }} />
                    <_RB.Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" />
                    <_RB.Line type="monotone" dataKey="filed" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                    <_RB.Line type="monotone" dataKey="fixed" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                  </_RB.LineChart>
                </_RB.ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card className="mt-4 p-4">
            <div className="flex items-start gap-4">
              <div className={cn('h-10 w-10 rounded-lg flex items-center justify-center shrink-0',
                release.blockers > 0 ? 'bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300'
                : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300')}>
                <Icon name={release.blockers > 0 ? 'shield-alert' : 'shield-check'} size={18} />
              </div>
              <div className="flex-1">
                <div className="font-semibold text-zinc-900 dark:text-zinc-100">Go / No-Go decision</div>
                <div className="text-[13px] text-zinc-500 mt-0.5">
                  {release.blockers > 0
                    ? `${release.blockers} open release-blocker${release.blockers === 1 ? '' : 's'} prevent sign-off. Resolve them in the issues view.`
                    : 'No blockers detected. The CTO can approve this release.'}
                </div>
                <div className="mt-3 flex items-center gap-1.5 text-[11.5px] text-zinc-500">
                  <Avatar user={userById('u7')} size={18} />
                  <span>Sajjad <RoleBadge value="cto" /></span>
                  <span>·</span>
                  <span>can sign off when blockers = 0</span>
                </div>
              </div>
            </div>
          </Card>

          <div className="mt-5 grid grid-cols-[1fr_320px] gap-4">
            <Card>
              <div className="px-5 pt-4">
                <div className="flex items-center justify-between">
                  <CardTitle>Issues in {release.version}</CardTitle>
                  <span className="text-[12px] text-zinc-500">{releaseIssues.length} issues</span>
                </div>
              </div>
              <IssueTable issues={releaseIssues.slice(0, 10)} onOpen={openIssue} hideRelease />
            </Card>

            {/* Release analytics card (replaces redundant release column) */}
            <div className="space-y-3">
              <Card className="p-4">
                <CardTitle>Top contributors</CardTitle>
                <CardDesc>This release</CardDesc>
                <ul className="mt-3 space-y-2">
                  {MOCK_CONTRIBUTIONS.filter(c => c.fixed > 0 || c.reported > 0).slice(0, 4).map(c => {
                    const u = userById(c.memberId);
                    return (
                      <li key={c.memberId} className="flex items-center gap-2 text-[12.5px]">
                        <Avatar user={u} size={22} />
                        <span className="font-medium text-zinc-900 dark:text-zinc-100 flex-1 truncate">{u.name}</span>
                        {c.fixed > 0 && <span className="inline-flex items-center gap-0.5 text-emerald-600 dark:text-emerald-400 font-semibold tabular-nums"><Icon name="check" size={11} />{c.fixed}</span>}
                        {c.reported > 0 && <span className="inline-flex items-center gap-0.5 text-blue-600 dark:text-blue-400 font-semibold tabular-nums"><Icon name="file-plus" size={11} />{c.reported}</span>}
                      </li>
                    );
                  })}
                </ul>
              </Card>

              <Card className="p-4">
                <CardTitle>Top affected components</CardTitle>
                <CardDesc>Where the bugs live</CardDesc>
                <ul className="mt-3 space-y-2.5">
                  {MOCK_FRAGILE.slice(0, 4).map(f => {
                    const pct = Math.min(100, (f.count / 5) * 100);
                    return (
                      <li key={f.component}>
                        <div className="flex items-center justify-between text-[12.5px] mb-1">
                          <LabelChip>{f.component}</LabelChip>
                          <span className="font-semibold tabular-nums">{f.count}</span>
                        </div>
                        <div className="h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full">
                          <div className="h-full bg-zinc-700 dark:bg-zinc-300 rounded-full" style={{ width: pct + '%' }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </Card>

              <Card className="p-4">
                <CardTitle>Triage velocity</CardTitle>
                <CardDesc>Time from filed → assigned</CardDesc>
                <div className="mt-2 grid grid-cols-2 gap-2 text-center">
                  <DashStat label="Blockers" value="0.6h" tone="red" />
                  <DashStat label="Critical" value="2.4h" tone="amber" />
                  <DashStat label="Major"    value="1.1d" />
                  <DashStat label="Minor"    value="3.2d" />
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  RELEASE REPORTS
// ─────────────────────────────────────────────────────────────────────────
function ReleaseReportsScreen() {
  return (
    <div className="px-7 py-6">
      <div className="mb-5">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Reports</div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">Release Reports</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Exportable summaries for every release that's shipped.</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {[
          { v: 'v2.4.1', proj: 'Core API',    range: 'May 12 – May 22, 2025', filed: 18, fixed: 16, verified: 14, deferred: 2, regressions: 3, status: 'in-progress' },
          { v: 'v2.3.0', proj: 'Core API',    range: 'Apr 16 – Apr 29, 2025', filed: 24, fixed: 24, verified: 24, deferred: 0, regressions: 2, status: 'shipped' },
          { v: 'v1.8.0', proj: 'Mobile App',  range: 'May 10 – May 20, 2025', filed: 9,  fixed: 5,  verified: 4,  deferred: 0, regressions: 1, status: 'in-progress' },
          { v: 'v1.7.2', proj: 'Mobile App',  range: 'Apr 26 – Apr 30, 2025', filed: 12, fixed: 12, verified: 12, deferred: 0, regressions: 1, status: 'shipped' },
        ].map(r => (
          <Card key={r.v}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="font-mono">{r.v}</CardTitle>
                    <Badge tone={r.status === 'shipped' ? 'green' : 'blue'}>{r.status}</Badge>
                  </div>
                  <CardDesc>{r.proj} · {r.range}</CardDesc>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm"><Icon name="file-text" size={11} /> View</Button>
                  <Dropdown trigger={<Button variant="outline" size="icon"><Icon name="ellipsis" size={13} /></Button>}>
                    <DropdownItem icon="download">Export PDF</DropdownItem>
                    <DropdownItem icon="file-text">Export CSV</DropdownItem>
                    <DropdownItem icon="share-2">Share link</DropdownItem>
                  </Dropdown>
                </div>
              </div>
            </CardHeader>
            <CardBody className="pt-0">
              <div className="grid grid-cols-5 gap-1 text-center">
                <Stat tone="blue" label="Filed" value={r.filed} />
                <Stat tone="green" label="Fixed" value={r.fixed} />
                <Stat tone="green" label="Verified" value={r.verified} />
                <Stat tone="default" label="Deferred" value={r.deferred} />
                <Stat tone="red" label="Regress." value={r.regressions} />
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, tone = 'default' }) {
  const tones = {
    default: 'text-zinc-900 dark:text-zinc-100',
    blue:  'text-blue-600 dark:text-blue-400',
    green: 'text-emerald-600 dark:text-emerald-400',
    red:   'text-red-600 dark:text-red-400',
  };
  return (
    <div className="rounded-md bg-zinc-50 dark:bg-zinc-900 px-2 py-2">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className={cn('text-base font-semibold tabular-nums', tones[tone])}>{value}</div>
    </div>
  );
}

Object.assign(window, { RegressionsScreen, ReleasesScreen, ReleaseReportsScreen, Stat });
