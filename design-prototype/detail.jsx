// ─── Issue detail — full page (no drawer) ──────────────────────────────────

function IssuePage({ issue, onClose, onUpdate }) {
  const toast = useToast();
  const [tab, setTab] = useState('activity');
  const [events, setEvents] = useState([]);
  const [showInternal, setShowInternal] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!issue) return;
    const base = MOCK_TIMELINE[issue.id] || [
      { id: 'a', type: 'filed', actor: issue.reporter, time: issue.filedAt },
      ...(issue.assignee ? [{ id: 'b', type: 'assigned', actor: 'u7', time: issue.filedAt, target: issue.assignee }] : []),
    ];
    setEvents(base);
    setTab('activity');
  }, [issue?.id]);

  if (!issue) return null;

  const assignee = userById(issue.assignee);
  const reporter = userById(issue.reporter);
  const visibleEvents = events.filter(e => showInternal || !e.internal);

  const addComment = ({ text, internal }) => {
    const next = {
      id: 'c' + Math.random().toString(36).slice(2,7),
      type: 'comment', actor: 'u7', time: new Date().toISOString().slice(0,16).replace('T',' '),
      text, internal,
    };
    setEvents(e => [...e, next]);
    const mention = /@([a-zA-Z0-9_.]+)/.exec(text);
    if (mention) {
      const u = userByUsername && userByUsername(mention[1]);
      toast({ title: `Comment posted on ${issue.id}`, body: `Notified ${mention[0]} in the thread`, target: u?.tg || '@' + mention[1] });
    }
  };

  const changeStatus = (newStatus) => {
    setEvents(e => [...e, { id: 'e' + Math.random().toString(36).slice(2,7), type: 'status_changed', actor: 'u7', time: 'now', from: issue.status, to: newStatus }]);
    onUpdate && onUpdate({ ...issue, status: newStatus });
    if (newStatus === 'fixed') {
      const r = userById(issue.reporter);
      toast({ title: `${issue.id} marked Fixed — verify requested`, target: r?.tg, warn: !r?.tgConnected });
    } else if (newStatus === 'verified') {
      const a = userById(issue.assignee);
      toast({ title: `${issue.id} verified — fix accepted`, target: a?.tg });
    }
  };

  const changeAssignee = (uId) => {
    setEvents(e => [...e, { id: 'a'+Math.random().toString(36).slice(2,7), type: 'assigned', actor: 'u7', time: 'now', target: uId }]);
    onUpdate && onUpdate({ ...issue, assignee: uId });
    const u = userById(uId);
    toast({ title: `${issue.id} assigned to ${u?.name}`, target: u?.tg, warn: !u?.tgConnected });
  };

  const copyLink = () => {
    const url = window.location.origin + window.location.pathname + '#/issue/' + issue.id;
    navigator.clipboard?.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header bar */}
      <div className="h-14 px-7 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-3 shrink-0 bg-white dark:bg-zinc-950">
        <button onClick={onClose} className="inline-flex items-center gap-1 text-[12px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 -ml-2 px-2 h-8 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
          <Icon name="chevron-left" size={13} /> Back to issues
        </button>
        <div className="h-5 w-px bg-zinc-200 dark:bg-zinc-800" />
        <div className="font-mono text-[12px] text-zinc-500">{issue.id}</div>
        <div className="flex items-center gap-1.5">
          <SeverityBadge value={issue.severity} dot />
          <StatusBadge value={issue.status} />
          {issue.regressions > 0 && (
            <Badge tone="red">
              <Icon name="refresh-ccw" size={10} />
              Regressed {issue.regressions}× · first seen v2.1
            </Badge>
          )}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <Tooltip content={copied ? 'Link copied' : 'Copy shareable link'}>
            <Button variant="outline" size="sm" onClick={copyLink}>
              <Icon name={copied ? 'check' : 'link'} size={12} /> {copied ? 'Copied' : 'Share'}
            </Button>
          </Tooltip>
          <Tooltip content="Previous (K)"><Button variant="ghost" size="icon"><Icon name="chevron-up" size={15} /></Button></Tooltip>
          <Tooltip content="Next (J)"><Button variant="ghost" size="icon"><Icon name="chevron-down" size={15} /></Button></Tooltip>
          <Dropdown
            trigger={<Button variant="ghost" size="icon"><Icon name="ellipsis" size={15} /></Button>}
          >
            <DropdownItem icon="copy">Mark duplicate…</DropdownItem>
            <DropdownItem icon="archive">Archive</DropdownItem>
            <DropdownSep />
            <DropdownItem icon="trash-2" danger>Delete</DropdownItem>
          </Dropdown>
        </div>
      </div>

      {/* Body — two columns */}
      <div className="flex-1 min-h-0 grid grid-cols-[1fr_320px]">
        {/* Left main */}
        <div className="overflow-y-auto px-7 py-6 max-w-[820px] mx-auto w-full">
          <h1 className="text-[22px] font-semibold leading-snug text-zinc-900 dark:text-zinc-100">{issue.title}</h1>
          <div className="mt-1.5 flex items-center gap-2 text-[12px] text-zinc-500 flex-wrap">
            <span>Filed by</span>
            <Avatar user={reporter} size={16} /> <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
            <RoleBadge value={issue.reporterRole} />
            <span>·</span>
            <span>{relTime(issue.filedAt)}</span>
            <span>·</span>
            <span className="font-mono">{issue.release}</span>
          </div>

          <div className="mt-4">
            <Tabs
              value={tab}
              onValueChange={setTab}
              options={[
                { value: 'activity',   label: 'Activity',    icon: 'activity', badge: events.length },
                { value: 'evidence',   label: 'Evidence',    icon: 'paperclip', badge: 3 },
                { value: 'regression', label: 'Regression history',  icon: 'refresh-ccw', badge: issue.regressions || null },
              ]}
            />
          </div>

          <div className="mt-5">
            {tab === 'activity' && (
              <>
                <DescriptionSection issue={issue} />
                <div className="my-6 border-t border-zinc-200 dark:border-zinc-800" />
                <IssueTimeline events={visibleEvents} onAddComment={addComment} />
              </>
            )}
            {tab === 'evidence' && <DescriptionSection issue={issue} />}
            {tab === 'regression' && <RegressionTimelineSection issue={issue} />}
          </div>
        </div>

        {/* Right metadata */}
        <aside className="border-l border-zinc-200 dark:border-zinc-800 overflow-y-auto bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-5 text-[13px]">
          <MetaRow label="Status">
            <Dropdown
              width={170}
              trigger={<button className="w-full text-left"><StatusBadge value={issue.status} /></button>}
            >
              {({ close }) => (
                <>
                  {Object.keys(STATUS).map(s => (
                    <DropdownItem key={s} onClick={() => { changeStatus(s); close(); }}>
                      <StatusBadge value={s} size="sm" />
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Severity">
            <Dropdown
              width={170}
              trigger={<button className="w-full text-left"><SeverityBadge value={issue.severity} dot /></button>}
            >
              {({ close }) => (
                <>
                  {Object.keys(SEVERITY).map(s => (
                    <DropdownItem key={s} onClick={() => { onUpdate && onUpdate({ ...issue, severity: s }); close(); }}>
                      <SeverityBadge value={s} dot size="sm" />
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Assignee">
            <Dropdown
              width={220}
              trigger={
                <button className="inline-flex items-center gap-2 text-zinc-800 dark:text-zinc-200">
                  {assignee
                    ? <><Avatar user={assignee} size={18} /><span>{assignee.name}</span></>
                    : <span className="text-zinc-400">Unassigned</span>}
                  <Icon name="chevron-down" size={12} className="text-zinc-400 ml-1" />
                </button>
              }
            >
              {({ close }) => (
                <>
                  <DropdownLabel>Assign to</DropdownLabel>
                  {MOCK_TEAM.filter(u => u.role === 'developer').map(u => (
                    <DropdownItem key={u.id} onClick={() => { changeAssignee(u.id); close(); }}>
                      <Avatar user={u} size={18} />
                      <div className="flex-1 flex items-center justify-between">
                        <span>{u.name}</span>
                        {!u.tgConnected && <Icon name="triangle-alert" size={11} className="text-amber-500" />}
                      </div>
                    </DropdownItem>
                  ))}
                </>
              )}
            </Dropdown>
          </MetaRow>

          <MetaRow label="Reporter">
            <div className="inline-flex items-center gap-2">
              <Avatar user={reporter} size={18} />
              <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
              <RoleBadge value={issue.reporterRole} />
            </div>
          </MetaRow>

          <MetaRow label="Release">
            <span className="font-mono text-zinc-800 dark:text-zinc-200">{issue.release}</span>
          </MetaRow>

          <MetaRow label="Project">
            <span className="text-zinc-700 dark:text-zinc-200">{MOCK_PROJECTS.find(p => p.id === issue.projectId)?.name}</span>
          </MetaRow>

          <MetaRow label="Labels">
            <div className="flex flex-wrap gap-1">
              {issue.labels.map(l => <LabelChip key={l}>{l}</LabelChip>)}
              <button className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800">
                <Icon name="plus" size={10} className="mr-0.5" /> Add
              </button>
            </div>
          </MetaRow>

          <MetaRow label="Release blocker">
            <Switch
              checked={issue.releaseBlocker}
              onChange={(v) => onUpdate && onUpdate({ ...issue, releaseBlocker: v })}
            />
          </MetaRow>

          {issue.mr && (
            <MetaRow label="Linked MR">
              <a className="inline-flex items-center gap-1 font-mono text-blue-600 dark:text-blue-400 hover:underline">
                <Icon name="git-merge" size={12} />{issue.mr}
              </a>
            </MetaRow>
          )}

          <div className="mt-4 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
            <TimeMetric label="Time in triage" value="0h 33m" tone="green" />
            <TimeMetric label="Time to fix" value={issue.timeToFixH ? `${issue.timeToFixH}h` : 'in-flight'} tone={issue.timeToFixH ? 'default' : 'amber'} />
            <TimeMetric label="Time to verify" value={issue.status === 'verified' ? '6h' : '—'} />
          </div>

          <div className="mt-5 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
            {issue.status !== 'fixed' && issue.status !== 'verified' && (
              <Button className="w-full" onClick={() => changeStatus('fixed')}>
                <Icon name="check" size={14} /> Mark as Fixed
              </Button>
            )}
            {issue.status === 'fixed' && (
              <Button variant="success" className="w-full" onClick={() => changeStatus('verified')}>
                <Icon name="shield-check" size={14} /> Verify fix
              </Button>
            )}
            {(issue.status === 'fixed' || issue.status === 'verified' || issue.status === 'closed') && (
              <Button variant="outline" className="w-full" onClick={() => changeStatus('regression')}>
                <Icon name="refresh-ccw" size={14} /> Mark as Regression
              </Button>
            )}
            <Button variant="outline" className="w-full" onClick={() => changeStatus('new')}>
              <Icon name="undo-2" size={14} /> Re-open
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function MetaRow({ label, children }) {
  return (
    <div className="grid grid-cols-[100px_1fr] items-start gap-2 py-1.5">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 pt-0.5">{label}</div>
      <div className="text-[12.5px] min-w-0">{children}</div>
    </div>
  );
}

function TimeMetric({ label, value, tone = 'default' }) {
  const tones = {
    default: 'text-zinc-800 dark:text-zinc-100',
    green: 'text-emerald-600 dark:text-emerald-400',
    amber: 'text-amber-600 dark:text-amber-400',
    red: 'text-red-600 dark:text-red-400',
  };
  return (
    <div className="flex items-center justify-between text-[12px]">
      <span className="text-zinc-500 dark:text-zinc-400">{label}</span>
      <span className={cn('font-medium tabular-nums', tones[tone])}>{value}</span>
    </div>
  );
}

function DescriptionSection({ issue }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Description</h3>
        <button className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1"><Icon name="pencil" size={11} />Edit</button>
      </div>
      <div className="text-[13.5px] text-zinc-700 dark:text-zinc-200 leading-relaxed md">
        <p>
          When two simultaneous wallet transfers hit the same source account within ~200ms,
          the second request returns a stale balance and the transfer is recorded twice.
          Reproduced consistently with the cURL below, and confirmed against the
          <code> staging-2</code> environment on build <code>sha:9a2e1f</code>.
        </p>
        <p>
          Expected: second request fails with <code>409 conflict / row lock not acquired</code>.
          Actual: both transfers succeed, leaving the source account in a negative state.
        </p>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 text-[11.5px]">
        <EnvTile icon="globe"   label="Browser" value={issue.env.browser} />
        <EnvTile icon="laptop"  label="OS"      value={issue.env.os} />
        <EnvTile icon="binary"  label="Build"   value={issue.env.build} mono />
        <EnvTile icon="server"  label="Stage"   value={issue.env.stage} mono />
        <EnvTile icon="tag"     label="Release" value={issue.release} mono />
        <EnvTile icon="map-pin" label="Region"  value="IR / production-proxy" />
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400">Repro: cURL</div>
          <button onClick={() => { navigator.clipboard?.writeText(CURL_SAMPLE); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
            className="inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
            <Icon name={copied ? 'check' : 'copy'} size={11} /> {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre className="rounded-lg bg-zinc-900 dark:bg-black text-zinc-100 px-4 py-3 text-[12px] font-mono leading-relaxed overflow-x-auto whitespace-pre">{CURL_SAMPLE}</pre>
      </div>

      <div className="mt-5">
        <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400 mb-1.5">Reproduction steps</div>
        <ol className="space-y-1.5 text-[13px] text-zinc-700 dark:text-zinc-200 list-decimal pl-5 marker:text-zinc-400">
          <li>Authenticate as <code className="font-mono text-[12px]">wallet_acct_8821</code> on <code>staging-2</code>.</li>
          <li>Open two tabs to the wallet UI and click "Transfer 12,500 IRR" within 200ms.</li>
          <li>Observe both responses return <code>200 OK</code> with identical <code>idempotency_key</code>.</li>
          <li>Refresh balance — the source account shows the funds debited twice.</li>
        </ol>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between mb-1.5">
          <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400">Attachments</div>
          <button className="inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"><Icon name="upload" size={11} /> Add</button>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <AttachmentTile kind="image" label="500-response.png" hint="JPG · 248 KB" />
          <AttachmentTile kind="video" label="screen-rec-082125.mp4" hint="MP4 · 1m 12s" />
          <AttachmentTile kind="file" label="server-trace.log" hint="LOG · 32 KB" />
        </div>
      </div>
    </div>
  );
}

function EnvTile({ icon, label, value, mono }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 px-2.5 py-2 bg-white dark:bg-zinc-950">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        <Icon name={icon} size={10} /> {label}
      </div>
      <div className={cn('text-[12.5px] mt-0.5 text-zinc-800 dark:text-zinc-100 truncate', mono && 'font-mono')}>{value}</div>
    </div>
  );
}

function AttachmentTile({ kind, label, hint }) {
  const iconMap = { image: 'image', video: 'play', file: 'file-text' };
  return (
    <button className="rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden text-left hover:border-zinc-400 dark:hover:border-zinc-600 transition-colors">
      <div className="aspect-[16/10] bg-zinc-100 dark:bg-zinc-900 flex items-center justify-center relative overflow-hidden">
        <svg className="absolute inset-0 w-full h-full text-zinc-200 dark:text-zinc-800" preserveAspectRatio="none">
          <defs>
            <pattern id={`stripes-${label}`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y="0" x2="0" y2="8" stroke="currentColor" strokeWidth="3" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill={`url(#stripes-${label})`} />
        </svg>
        <div className="relative h-7 w-7 rounded-full bg-white dark:bg-zinc-950 shadow flex items-center justify-center text-zinc-700 dark:text-zinc-200">
          <Icon name={iconMap[kind] || 'file'} size={13} />
        </div>
      </div>
      <div className="px-2 py-1.5">
        <div className="text-[12px] font-medium text-zinc-800 dark:text-zinc-100 truncate">{label}</div>
        <div className="text-[10px] text-zinc-500">{hint}</div>
      </div>
    </button>
  );
}

// ───── NEW vertical regression history timeline ─────
function RegressionTimelineSection({ issue }) {
  const log = (MOCK_REGRESSION_LOG && MOCK_REGRESSION_LOG[issue.id]) || [];
  // group by release
  const groups = useMemo(() => {
    const byRel = {};
    for (const ev of log) {
      if (!byRel[ev.release]) byRel[ev.release] = [];
      byRel[ev.release].push(ev);
    }
    // preserve insertion order from log (chronological)
    const ordered = [];
    const seen = new Set();
    for (const ev of log) {
      if (!seen.has(ev.release)) { seen.add(ev.release); ordered.push({ release: ev.release, events: byRel[ev.release] }); }
    }
    return ordered;
  }, [log]);

  const totalRegressions = log.filter(e => e.kind === 'regression').length;
  const fixes = log.filter(e => e.kind === 'fixed').length;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Regression history</h3>
          <p className="text-[13px] text-zinc-600 dark:text-zinc-300 mt-1">
            Every fix attempt and every reappearance, with dates and notes. Grouped by release.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11.5px]">
          <Badge tone="red"><Icon name="refresh-ccw" size={10} /> {totalRegressions} regression{totalRegressions === 1 ? '' : 's'}</Badge>
          <Badge tone="green"><Icon name="check" size={10} /> {fixes} fix attempts</Badge>
        </div>
      </div>

      {/* Vertical timeline grouped by release */}
      <ol className="relative pl-2 mt-1">
        {groups.map((g, gi) => (
          <li key={g.release} className="relative pl-8">
            {/* Release marker */}
            <span className="absolute left-0 top-1 h-5 w-5 rounded-md bg-white dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 flex items-center justify-center text-[9px] font-bold text-zinc-700 dark:text-zinc-200">
              <Icon name="tag" size={10} />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[14px] font-semibold text-zinc-900 dark:text-zinc-100">{g.release}</span>
              <span className="text-[11px] text-zinc-500">{g.events.length} event{g.events.length === 1 ? '' : 's'}</span>
            </div>

            <ol className="relative mt-2 mb-5 pl-4 border-l-2 border-zinc-200 dark:border-zinc-800 space-y-3">
              {g.events.map(ev => <RegEventRow key={ev.id} ev={ev} />)}
            </ol>
          </li>
        ))}
      </ol>

      <div className="mt-2 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50">
        <div className="flex items-start gap-3">
          <div className="h-8 w-8 rounded-lg bg-amber-100 dark:bg-amber-900/60 flex items-center justify-center text-amber-700 dark:text-amber-300 shrink-0">
            <Icon name="lightbulb" size={14} />
          </div>
          <div className="text-[13px] flex-1">
            <div className="font-semibold text-amber-900 dark:text-amber-200">Pattern: same code path, different entry points</div>
            <div className="text-amber-800 dark:text-amber-300 mt-1 leading-relaxed">
              {totalRegressions} regressions over the wallet transfer flow — each one a different caller (single transfer, retry job, batch endpoint).
              The fix history suggests adding a transfer-service-wide invariant test, not just patching new callers.
            </div>
            <Button size="sm" variant="outline" className="mt-3">
              Suggest test coverage <Icon name="arrow-up-right" size={11} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function RegEventRow({ ev }) {
  const actor = userById(ev.actor);
  const styles = {
    fixed:       { bg: 'bg-emerald-100 dark:bg-emerald-950/50', text: 'text-emerald-700 dark:text-emerald-300', icon: 'check',       label: 'Fixed' },
    regression:  { bg: 'bg-red-100 dark:bg-red-950/50',         text: 'text-red-700 dark:text-red-300',         icon: 'refresh-ccw', label: 'Regression' },
    verified:    { bg: 'bg-green-100 dark:bg-green-950/50',     text: 'text-green-700 dark:text-green-300',     icon: 'shield-check', label: 'Verified' },
    'in-progress':{ bg: 'bg-indigo-100 dark:bg-indigo-950/50', text: 'text-indigo-700 dark:text-indigo-300',   icon: 'loader-circle', label: 'In progress' },
    open:        { bg: 'bg-amber-100 dark:bg-amber-950/50',     text: 'text-amber-700 dark:text-amber-300',     icon: 'circle-dot',  label: 'Reopened' },
  }[ev.kind] || { bg: 'bg-zinc-100 dark:bg-zinc-800', text: 'text-zinc-600 dark:text-zinc-300', icon: 'circle', label: ev.kind };
  return (
    <li className="relative">
      <span className={cn('absolute -left-[26px] top-0.5 h-4 w-4 rounded-full ring-4 ring-white dark:ring-zinc-950 flex items-center justify-center', styles.bg, styles.text)}>
        <Icon name={styles.icon} size={9} strokeWidth={2.6} />
      </span>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={cn('inline-flex items-center gap-1 rounded px-1.5 py-0 text-[10.5px] font-semibold uppercase tracking-wide', styles.bg, styles.text)}>
          {styles.label}
        </span>
        {actor && (
          <span className="inline-flex items-center gap-1 text-[12px] text-zinc-700 dark:text-zinc-200">
            <Avatar user={actor} size={14} />
            <span className="font-medium">{actor.name}</span>
          </span>
        )}
        {ev.mr && (
          <span className="inline-flex items-center rounded bg-blue-50 dark:bg-blue-950/40 px-1.5 py-0.5 text-[10.5px] font-mono text-blue-700 dark:text-blue-300">
            <Icon name="git-merge" size={9} className="mr-0.5" /> MR {ev.mr}
          </span>
        )}
        <span className="ml-auto text-[11px] text-zinc-400 font-mono tabular-nums">{ev.date}</span>
      </div>
      {ev.note && (
        <div className="mt-1 text-[13px] text-zinc-700 dark:text-zinc-200 leading-snug">{ev.note}</div>
      )}
    </li>
  );
}

Object.assign(window, { IssuePage, RegressionTimelineSection, DescriptionSection });
