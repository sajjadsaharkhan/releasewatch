// ─── Profile screen — public view + private edit ───────────────────────────

const _RP = window.Recharts;

function ProfileScreen({ userId, openIssue }) {
  const meId = 'u7';
  const isMe = userId === meId;
  const user = userById(userId) || userById(meId);
  const [tab, setTab] = useState('public');
  const [edit, setEdit] = useState({
    name: user.name, username: user.username, email: user.email || (user.username + '@releasewatch.dev'),
    title: user.title || '', bio: user.bio || '', location: user.location || '',
    tg: user.tg, password: '', newPassword: '',
  });
  const toast = useToast();

  // Derived "performance metrics" by role
  const contrib = MOCK_CONTRIBUTIONS.find(c => c.memberId === userId) || { reported: 0, fixed: 0, avgFixH: null, regressionsCaused: 0, fixRate: null, repBySev: {} };
  const reportedIssues = MOCK_ISSUES.filter(i => i.reporter === userId);
  const assignedIssues = MOCK_ISSUES.filter(i => i.assignee === userId);
  const fixedIssues    = assignedIssues.filter(i => i.status === 'fixed' || i.status === 'verified');

  const series = useMemo(() => ([
    { day: 'Mon', filed: contrib.reported >= 5 ? 3 : 1, fixed: contrib.fixed >= 5 ? 1 : 0 },
    { day: 'Tue', filed: contrib.reported >= 5 ? 2 : 1, fixed: contrib.fixed >= 5 ? 2 : 0 },
    { day: 'Wed', filed: contrib.reported >= 5 ? 4 : 1, fixed: contrib.fixed >= 5 ? 1 : 0 },
    { day: 'Thu', filed: contrib.reported >= 5 ? 2 : 0, fixed: contrib.fixed >= 5 ? 3 : 1 },
    { day: 'Fri', filed: contrib.reported >= 5 ? 2 : 1, fixed: contrib.fixed >= 5 ? 2 : 1 },
    { day: 'Sat', filed: 1, fixed: contrib.fixed >= 5 ? 1 : 0 },
    { day: 'Sun', filed: 0, fixed: contrib.fixed >= 5 ? 1 : 0 },
  ]), [contrib]);

  const copyProfileLink = () => {
    const url = window.location.origin + window.location.pathname + '#/u/' + user.username;
    navigator.clipboard?.writeText(url);
    toast({ title: 'Public profile link copied', body: url.replace(window.location.origin, ''), target: '@' + user.username });
  };

  return (
    <div className="px-7 py-6 max-w-5xl mx-auto w-full">
      {/* Header cover */}
      <div className="rounded-xl bg-gradient-to-br from-zinc-100 to-zinc-50 dark:from-zinc-900 dark:to-zinc-950 border border-zinc-200 dark:border-zinc-800 p-5">
        <div className="flex items-start gap-5">
          <Avatar user={user} size={84} ring />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{user.name}</h1>
              <RoleBadge value={user.role} />
              {user.tgConnected && <Badge tone="green"><Icon name="check" size={10} /> Telegram</Badge>}
            </div>
            <div className="text-[13.5px] text-zinc-500 mt-1 inline-flex items-center gap-2 flex-wrap">
              <span className="font-mono">@{user.username}</span>
              {user.title && <><span>·</span><span>{user.title}</span></>}
              {user.location && <><span>·</span><span className="inline-flex items-center gap-1"><Icon name="map-pin" size={12} /> {user.location}</span></>}
            </div>
            {user.bio && <p className="text-[13.5px] text-zinc-700 dark:text-zinc-200 mt-2 max-w-2xl leading-snug">{user.bio}</p>}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" onClick={copyProfileLink}><Icon name="link" size={12} /> Copy public link</Button>
            {isMe && <Button size="sm" onClick={() => setTab('edit')}><Icon name="pencil" size={12} /> Edit profile</Button>}
          </div>
        </div>

        {/* Hero stats */}
        <div className="grid grid-cols-4 gap-2 mt-5">
          <HeroStat label="Reported" value={contrib.reported} icon="file-plus" tone="blue" />
          <HeroStat label="Fixed"    value={contrib.fixed}    icon="check"     tone="green" />
          <HeroStat label="Avg fix time" value={contrib.avgFixH ? contrib.avgFixH + 'h' : '—'} icon="zap" />
          <HeroStat label="Fix rate"     value={contrib.fixRate != null ? contrib.fixRate + '%' : '—'} icon="trending-up" tone={contrib.fixRate >= 95 ? 'green' : contrib.fixRate >= 85 ? 'amber' : 'default'} />
        </div>
      </div>

      <div className="mt-5">
        <Tabs
          value={tab}
          onValueChange={setTab}
          options={[
            { value: 'public',    label: 'Public profile',  icon: 'user' },
            { value: 'assigned',  label: 'Assigned issues', icon: 'bug',  badge: assignedIssues.length },
            { value: 'reported',  label: 'Reported issues', icon: 'file-plus', badge: reportedIssues.length },
            ...(isMe ? [{ value: 'edit',      label: 'Edit',            icon: 'pencil' }] : []),
            ...(isMe ? [{ value: 'security',  label: 'Security',        icon: 'shield' }] : []),
          ]}
        />
      </div>

      <div className="mt-5">
        {tab === 'public' && (
          <div className="grid grid-cols-[1fr_280px] gap-4">
            {/* Activity chart */}
            <Card>
              <CardHeader>
                <CardTitle>Activity this release</CardTitle>
                <CardDesc>Bugs filed vs fixed per day, v2.4.1</CardDesc>
              </CardHeader>
              <div className="px-2 pb-3" style={{ height: 240 }}>
                <_RP.ResponsiveContainer width="100%" height="100%">
                  <_RP.LineChart data={series} margin={{ top: 10, right: 16, bottom: 0, left: -10 }}>
                    <_RP.CartesianGrid stroke="rgba(150,150,150,0.15)" vertical={false} />
                    <_RP.XAxis dataKey="day" tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
                    <_RP.YAxis tick={{ fontSize: 11, fill: '#71717a' }} axisLine={false} tickLine={false} />
                    <_RP.Tooltip contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e4e4e7' }} />
                    <_RP.Legend wrapperStyle={{ fontSize: 11 }} />
                    <_RP.Line type="monotone" dataKey="filed" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                    <_RP.Line type="monotone" dataKey="fixed" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                  </_RP.LineChart>
                </_RP.ResponsiveContainer>
              </div>
            </Card>

            {/* Role-aware sidebar */}
            <Card>
              <CardHeader><CardTitle>By severity</CardTitle><CardDesc>{user.role === 'developer' ? 'Issues fixed' : 'Issues reported'}</CardDesc></CardHeader>
              <CardBody className="pt-0 space-y-2.5">
                {['blocker','critical','major','minor','enhancement'].map(s => {
                  const n = contrib.repBySev?.[s] || 0;
                  const total = Object.values(contrib.repBySev || {}).reduce((a,b) => a+b, 0) || 1;
                  const pct = (n / total) * 100;
                  return (
                    <div key={s}>
                      <div className="flex items-center justify-between text-[12px] mb-1">
                        <SeverityBadge value={s} size="sm" dot />
                        <span className="font-semibold tabular-nums">{n}</span>
                      </div>
                      <div className="h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full">
                        <div className={cn('h-full rounded-full', SEVERITY[s].dot)} style={{ width: pct + '%' }} />
                      </div>
                    </div>
                  );
                })}
              </CardBody>
            </Card>
          </div>
        )}

        {tab === 'assigned' && (
          <Card className="overflow-hidden">
            <IssueTable issues={assignedIssues} onOpen={openIssue} />
            {assignedIssues.length === 0 && <Empty icon="check-check" title="No assigned issues" body="Inbox zero on assignments." />}
          </Card>
        )}
        {tab === 'reported' && (
          <Card className="overflow-hidden">
            <IssueTable issues={reportedIssues} onOpen={openIssue} />
            {reportedIssues.length === 0 && <Empty icon="file-plus" title="No issues reported" />}
          </Card>
        )}

        {tab === 'edit' && isMe && (
          <Card className="p-5 max-w-2xl space-y-4">
            <CardTitle>Edit profile</CardTitle>
            <CardDesc>This is what your team sees. Username is used for @mentions, login, and shareable profile links.</CardDesc>
            <Field label="Full name"><Input value={edit.name} onChange={(e) => setEdit(s => ({ ...s, name: e.target.value }))} /></Field>
            <Field label="Username" hint={`Profile URL: /u/${edit.username || 'username'}`}>
              <div className="flex items-center gap-1">
                <span className="text-zinc-400 font-mono text-[13px]">@</span>
                <Input value={edit.username} onChange={(e) => setEdit(s => ({ ...s, username: e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, '') }))} className="font-mono" />
              </div>
            </Field>
            <Field label="Title"><Input value={edit.title} onChange={(e) => setEdit(s => ({ ...s, title: e.target.value }))} /></Field>
            <Field label="Email"><Input value={edit.email} onChange={(e) => setEdit(s => ({ ...s, email: e.target.value }))} /></Field>
            <Field label="Location"><Input value={edit.location} onChange={(e) => setEdit(s => ({ ...s, location: e.target.value }))} /></Field>
            <Field label="Bio"><Textarea rows={3} value={edit.bio} onChange={(e) => setEdit(s => ({ ...s, bio: e.target.value }))} /></Field>
            <Field label="Telegram" hint={user.tgConnected ? 'Connected. /disconnect in Telegram to revoke.' : 'Send /connect in @ReleasewatchBot to link.'}>
              <div className="flex items-center gap-2">
                <Input value={edit.tg} onChange={(e) => setEdit(s => ({ ...s, tg: e.target.value }))} className="font-mono" />
                {user.tgConnected
                  ? <Badge tone="green"><Icon name="check" size={10} /> Connected</Badge>
                  : <Badge tone="amber"><Icon name="clock" size={10} /> Pending</Badge>}
              </div>
            </Field>
            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
              <Button variant="outline">Cancel</Button>
              <Button onClick={() => toast({ title: 'Profile updated', body: 'Your changes are live for the team', target: edit.tg })}><Icon name="save" size={12} /> Save</Button>
            </div>
          </Card>
        )}

        {tab === 'security' && isMe && (
          <Card className="p-5 max-w-2xl space-y-4">
            <CardTitle>Security</CardTitle>
            <CardDesc>Password + 2FA + sessions.</CardDesc>
            <Field label="Current password"><Input type="password" placeholder="••••••••" /></Field>
            <Field label="New password"><Input type="password" placeholder="At least 12 chars" /></Field>
            <Field label="Confirm new"><Input type="password" placeholder="Repeat new password" /></Field>
            <div className="flex items-center justify-between pt-3 border-t border-zinc-200 dark:border-zinc-800">
              <div className="flex items-center gap-2 text-[12.5px] text-zinc-600 dark:text-zinc-300">
                <Icon name="shield-check" size={14} className="text-emerald-500" /> 2FA enabled via Telegram
              </div>
              <Button onClick={() => toast({ title: 'Password updated', body: 'Existing sessions will stay signed in', target: user.tg })}><Icon name="key-round" size={12} /> Update password</Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function HeroStat({ label, value, icon, tone = 'default' }) {
  const tones = {
    default: 'text-zinc-900 dark:text-zinc-100',
    blue:    'text-blue-600 dark:text-blue-400',
    green:   'text-emerald-600 dark:text-emerald-400',
    amber:   'text-amber-600 dark:text-amber-400',
  };
  return (
    <div className="rounded-lg bg-white/70 dark:bg-zinc-950/60 border border-zinc-200 dark:border-zinc-800 px-3 py-2.5">
      <div className="flex items-center gap-1 text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        <Icon name={icon} size={11} /> {label}
      </div>
      <div className={cn('text-[20px] font-semibold tabular-nums mt-0.5', tones[tone])}>{value}</div>
    </div>
  );
}

Object.assign(window, { ProfileScreen });
