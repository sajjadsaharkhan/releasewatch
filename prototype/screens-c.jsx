// ─── Screens part C: Settings, Team, NewIssue modal ────────────────────────

// ─────────────────────────────────────────────────────────────────────────
//  SETTINGS
// ─────────────────────────────────────────────────────────────────────────
function SettingsScreen() {
  const [tab, setTab] = useState('integrations');
  const toast = useToast();

  return (
    <div className="px-7 py-6">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Settings</h1>
      <div className="border-b border-zinc-200 dark:border-zinc-800 mb-5">
        <div className="flex items-center gap-1">
          {[
            { v: 'general',       l: 'General' },
            { v: 'team',          l: 'Team' },
            { v: 'projects',      l: 'Projects' },
            { v: 'labels',        l: 'Labels' },
            { v: 'integrations',  l: 'Integrations' },
            { v: 'notifications', l: 'Notifications' },
          ].map(t => (
            <button key={t.v} onClick={() => setTab(t.v)}
              className={cn('px-3 h-9 text-[13px] font-medium relative -mb-px border-b-2',
                tab === t.v ? 'text-zinc-900 dark:text-zinc-100 border-zinc-900 dark:border-zinc-100' : 'text-zinc-500 border-transparent hover:text-zinc-900 dark:hover:text-zinc-100')}>
              {t.l}
            </button>
          ))}
        </div>
      </div>

      {tab === 'general' && <GeneralSettings />}
      {tab === 'team' && <TeamSettings />}
      {tab === 'projects' && <ProjectsSettings />}
      {tab === 'labels' && <LabelsSettings />}
      {tab === 'integrations' && <IntegrationsSettings onTest={() => toast({ title: 'Telegram bot reachable', body: '@ReleasewatchBot · 200 OK · 84ms', target: '@ReleasewatchBot' })} />}
      {tab === 'notifications' && <NotificationsSettings />}
    </div>
  );
}

function GeneralSettings() {
  return (
    <div className="max-w-2xl space-y-5">
      <Card>
        <CardHeader><CardTitle>Workspace</CardTitle></CardHeader>
        <CardBody className="space-y-3">
          <Field label="Company name"><Input defaultValue="Releasewatch Inc." /></Field>
          <Field label="Default timezone">
            <NativeSelect defaultValue="Asia/Tehran">
              <option>Asia/Tehran (IRST)</option><option>UTC</option><option>America/Los_Angeles</option>
            </NativeSelect>
          </Field>
          <Field label="Logo">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-lg bg-zinc-900 dark:bg-zinc-100 flex items-center justify-center text-white dark:text-zinc-900"><Icon name="radar" size={20} /></div>
              <Button variant="outline" size="sm"><Icon name="upload" size={12} /> Upload</Button>
            </div>
          </Field>
        </CardBody>
      </Card>
    </div>
  );
}

function Field({ label, children, hint }) {
  return (
    <div className="grid grid-cols-[160px_1fr] gap-3 items-start">
      <div>
        <div className="text-[12.5px] font-medium text-zinc-700 dark:text-zinc-200">{label}</div>
        {hint && <div className="text-[11px] text-zinc-500 mt-0.5">{hint}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
}

function TeamSettings() {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{MOCK_TEAM.length} members</h3>
        <Button size="sm"><Icon name="plus" size={12} /> Invite member</Button>
      </div>
      <Card>
        <table className="w-full text-[13px]">
          <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
            <tr>
              <th className="text-left font-medium px-4 py-2">Name</th>
              <th className="text-left font-medium px-2 py-2">Username</th>
              <th className="text-left font-medium px-2 py-2">Role</th>
              <th className="text-left font-medium px-2 py-2">Telegram</th>
              <th className="text-left font-medium px-2 py-2">Status</th>
              <th className="text-right font-medium px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {MOCK_TEAM.map(u => (
              <tr key={u.id} className="border-b border-zinc-100 dark:border-zinc-900 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
                <td className="px-4 py-2">
                  <div className="flex items-center gap-2">
                    <Avatar user={u} size={24} />
                    <div>
                      <div className="font-medium text-zinc-900 dark:text-zinc-100">{u.name}</div>
                      <div className="text-[10.5px] text-zinc-500">{u.title}</div>
                    </div>
                  </div>
                </td>
                <td className="px-2 py-2 font-mono text-[12px] text-zinc-600 dark:text-zinc-300">@{u.username}</td>
                <td className="px-2 py-2"><RoleBadge value={u.role} /></td>
                <td className="px-2 py-2 font-mono text-[12px] text-zinc-600 dark:text-zinc-300">{u.tg}</td>
                <td className="px-2 py-2">
                  {u.tgConnected
                    ? <Badge tone="green"><Icon name="check" size={10} /> Connected</Badge>
                    : <Badge tone="amber"><Icon name="clock" size={10} /> Pending</Badge>}
                </td>
                <td className="px-4 py-2 text-right">
                  <Dropdown trigger={<Button variant="ghost" size="icon"><Icon name="ellipsis" size={13} /></Button>}>
                    <DropdownItem icon="user">Open profile</DropdownItem>
                    <DropdownItem icon="pencil">Edit</DropdownItem>
                    <DropdownItem icon="key-round">Reset Telegram token</DropdownItem>
                    <DropdownSep />
                    <DropdownItem icon="user-minus" danger>Remove</DropdownItem>
                  </Dropdown>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* Invite member form */}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Invite a new member</CardTitle>
          <CardDesc>They will receive an email + a Telegram /connect token to claim their account.</CardDesc>
        </CardHeader>
        <CardBody className="pt-0 grid grid-cols-[1fr_1fr_1fr_140px_120px] gap-2 items-end">
          <FieldInline label="Full name"><Input placeholder="Yousef A." /></FieldInline>
          <FieldInline label="Username"><Input placeholder="yousef.a" className="font-mono" /></FieldInline>
          <FieldInline label="Email"><Input placeholder="yousef@releasewatch.dev" /></FieldInline>
          <FieldInline label="Role"><NativeSelect><option>Developer</option><option>QA</option><option>CTO</option><option>Admin</option></NativeSelect></FieldInline>
          <Button><Icon name="send" size={12} /> Invite</Button>
        </CardBody>
      </Card>
    </div>
  );
}

function ProjectsSettings() {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{MOCK_PROJECTS.length} projects</h3>
        <Button size="sm"><Icon name="plus" size={12} /> New project</Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {MOCK_PROJECTS.map(p => (
          <Card key={p.id} className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center font-bold">{p.name[0]}</div>
                <div>
                  <div className="text-[14px] font-semibold text-zinc-900 dark:text-zinc-100">{p.name}</div>
                  <div className="text-[12px] text-zinc-500">{p.desc}</div>
                </div>
              </div>
              <Dropdown trigger={<Button variant="ghost" size="icon"><Icon name="ellipsis" size={13} /></Button>}>
                <DropdownItem icon="pencil">Edit</DropdownItem>
                <DropdownItem icon="archive">Archive</DropdownItem>
              </Dropdown>
            </div>
            <div className="mt-3 flex items-center gap-4 text-[11.5px] text-zinc-500">
              <span>{MOCK_RELEASES.filter(r => r.projectId === p.id).length} releases</span>
              <span>{MOCK_ISSUES.filter(i => i.projectId === p.id).length} issues</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function IntegrationsSettings({ onTest }) {
  const [showToken, setShowToken] = useState(false);
  return (
    <div className="max-w-3xl space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 rounded-lg bg-[#2AABEE] flex items-center justify-center text-white">
                <Icon name="send" size={18} />
              </div>
              <div>
                <CardTitle>Telegram bot</CardTitle>
                <CardDesc>The only notification channel · @ReleasewatchBot</CardDesc>
              </div>
            </div>
            <Badge tone="green"><Icon name="check" size={10} /> Connected</Badge>
          </div>
        </CardHeader>
        <CardBody className="pt-0 space-y-4">
          <Field label="Bot token">
            <div className="flex items-center gap-2">
              <Input type={showToken ? 'text' : 'password'} defaultValue="7621948322:AAEh7B9_QkkV7M9hQc—•••" className="font-mono" />
              <Button variant="outline" size="icon" onClick={() => setShowToken(s => !s)}>
                <Icon name={showToken ? 'eye-off' : 'eye'} size={14} />
              </Button>
              <Button variant="outline" size="sm" onClick={onTest}><Icon name="send" size={12} /> Test</Button>
            </div>
          </Field>

          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-4">
            <div className="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100 mb-2">Connect your personal Telegram</div>
            <ol className="text-[12.5px] text-zinc-600 dark:text-zinc-300 space-y-1.5 list-decimal pl-5 marker:text-zinc-400">
              <li>Open <a className="text-blue-600 dark:text-blue-400">@ReleasewatchBot</a> in Telegram.</li>
              <li>Send the command: <code className="font-mono bg-white dark:bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-200 dark:border-zinc-800">/connect rw_user_aGc1z–4Pe</code></li>
              <li>You'll receive a confirmation. Notifications will start arriving immediately.</li>
            </ol>
          </div>

          <div>
            <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400 mb-2">Connected users</div>
            <div className="grid grid-cols-2 gap-2">
              {MOCK_TEAM.map(u => (
                <div key={u.id} className="flex items-center gap-2 px-3 py-2 rounded-md border border-zinc-200 dark:border-zinc-800">
                  <Avatar user={u} size={22} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] font-medium text-zinc-900 dark:text-zinc-100 truncate">{u.name}</div>
                    <div className="text-[10.5px] text-zinc-500 font-mono">{u.tg}</div>
                  </div>
                  {u.tgConnected
                    ? <Icon name="check-circle-2" size={14} className="text-emerald-500" />
                    : <Icon name="clock" size={14} className="text-amber-500" />}
                </div>
              ))}
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <div className="h-10 w-10 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center">
                <Icon name="webhook" size={18} />
              </div>
              <div>
                <CardTitle>Webhooks</CardTitle>
                <CardDesc>Send issue events to your own endpoint — BYO integration</CardDesc>
              </div>
            </div>
            <Badge tone="muted">Optional</Badge>
          </div>
        </CardHeader>
        <CardBody className="pt-0">
          <Field label="Endpoint URL">
            <Input placeholder="https://hooks.your-tool.com/releasewatch" className="font-mono text-[12px]" />
          </Field>
        </CardBody>
      </Card>
    </div>
  );
}

const NOTIFICATIONS = [
  { event: 'Issue filed (blocker)', reporter: false, assignee: false, triage: true,  cto: true  },
  { event: 'Issue assigned',        reporter: false, assignee: true,  triage: false, cto: false },
  { event: 'Comment / mention',     reporter: true,  assignee: true,  triage: true,  cto: true  },
  { event: 'Issue fixed',           reporter: true,  assignee: false, triage: false, cto: false },
  { event: 'Fix verified',          reporter: false, assignee: true,  triage: false, cto: false },
  { event: 'Regression detected',   reporter: true,  assignee: true,  triage: true,  cto: true  },
  { event: 'Release approved',      reporter: false, assignee: false, triage: true,  cto: false },
  { event: 'Release blocked',       reporter: false, assignee: false, triage: true,  cto: false },
];

function NotificationsSettings() {
  const [matrix, setMatrix] = useState(NOTIFICATIONS);
  const toggle = (i, col) => setMatrix(m => m.map((r, idx) => idx === i ? { ...r, [col]: !r[col] } : r));

  return (
    <div className="grid grid-cols-[1fr_360px] gap-5">
      <Card>
        <CardHeader>
          <CardTitle>Telegram notification matrix</CardTitle>
          <CardDesc>Who gets pinged when. All notifications route through @ReleasewatchBot.</CardDesc>
        </CardHeader>
        <table className="w-full text-[13px]">
          <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-y border-zinc-200 dark:border-zinc-800">
            <tr>
              <th className="text-left font-medium px-4 py-2">Event</th>
              <th className="text-center font-medium px-2 py-2">Reporter</th>
              <th className="text-center font-medium px-2 py-2">Assignee</th>
              <th className="text-center font-medium px-2 py-2">Triage</th>
              <th className="text-center font-medium px-4 py-2">CTO</th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((r, i) => (
              <tr key={r.event} className="border-b border-zinc-100 dark:border-zinc-900 last:border-0">
                <td className="px-4 py-2 text-zinc-800 dark:text-zinc-100">{r.event}</td>
                <td className="px-2 py-2 text-center"><Switch checked={r.reporter} onChange={() => toggle(i, 'reporter')} className="mx-auto" /></td>
                <td className="px-2 py-2 text-center"><Switch checked={r.assignee} onChange={() => toggle(i, 'assignee')} className="mx-auto" /></td>
                <td className="px-2 py-2 text-center"><Switch checked={r.triage}   onChange={() => toggle(i, 'triage')} className="mx-auto" /></td>
                <td className="px-4 py-2 text-center"><Switch checked={r.cto}      onChange={() => toggle(i, 'cto')} className="mx-auto" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-2">Telegram preview</div>
        <div className="space-y-3">
          <TelegramPreview kind="blocker" />
          <TelegramPreview kind="assigned" />
          <TelegramPreview kind="fixed" />
          <TelegramPreview kind="regression" />
        </div>
      </div>
    </div>
  );
}

function TelegramPreview({ kind }) {
  const map = {
    blocker:    { emoji: '🐛', title: 'New BLOCKER filed: BUG-052', body: 'Wallet sync crash on concurrent txn', meta: 'Reporter: Maryam K. (QA) · Release v2.4.1' },
    assigned:   { emoji: '👤', title: 'Assigned to you: BUG-042', body: 'Wallet sync fails on concurrent transactions', meta: 'Assigned by Sajjad · Release v2.4.1' },
    fixed:      { emoji: '✅', title: 'BUG-039 marked Fixed', body: 'Auth token not refreshed on session resume', meta: 'Fixed by Kamran J. · MR !204 — please verify' },
    regression: { emoji: '↻',  title: 'Regression detected: BUG-042', body: 'Wallet sync fix did not hold in v2.4.1', meta: 'Reopened by Maryam K. · 3rd regression' },
  };
  const m = map[kind];
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
      <div className="px-3 py-2 bg-[#2AABEE]/10 dark:bg-[#2AABEE]/15 flex items-center gap-2">
        <div className="h-6 w-6 rounded-full bg-[#2AABEE] text-white flex items-center justify-center text-[12px]"><Icon name="send" size={12} /></div>
        <div>
          <div className="text-[11.5px] font-semibold text-zinc-900 dark:text-zinc-100">Releasewatch · Core API</div>
          <div className="text-[10px] text-zinc-500">@ReleasewatchBot</div>
        </div>
        <span className="ml-auto text-[10px] text-zinc-400">now</span>
      </div>
      <div className="px-3 py-2.5">
        <div className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{m.emoji} {m.title}</div>
        <div className="text-[12.5px] text-zinc-700 dark:text-zinc-200 mt-0.5">{m.body}</div>
        <div className="mt-2 text-[11px] text-zinc-500">{m.meta}</div>
        <button className="mt-2 text-[12px] font-medium text-blue-600 dark:text-blue-400 inline-flex items-center gap-1">View issue <Icon name="arrow-up-right" size={11} /></button>
      </div>
    </div>
  );
}

function TeamScreen({ openProfile }) {
  return (
    <div className="px-7 py-6 max-w-5xl">
      <div className="flex items-end justify-between mb-1">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">Team</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Who's filing, fixing, and verifying — click anyone to see their profile.</p>
        </div>
        <Button size="sm"><Icon name="plus" size={12} /> Invite member</Button>
      </div>

      {/* Member cards */}
      <div className="mt-5 grid grid-cols-3 gap-3">
        {MOCK_TEAM.map(u => {
          const c = MOCK_CONTRIBUTIONS.find(c => c.memberId === u.id) || { reported: 0, fixed: 0 };
          return (
            <button key={u.id} onClick={() => openProfile && openProfile(u)} className="text-left">
              <Card className="p-4 hover:shadow-md transition-shadow h-full">
                <div className="flex items-start gap-3">
                  <Avatar user={u} size={44} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-semibold text-zinc-900 dark:text-zinc-100 truncate">{u.name}</div>
                    <div className="text-[11.5px] text-zinc-500 truncate">{u.title}</div>
                    <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
                      <RoleBadge value={u.role} />
                      <span className="text-[11px] text-zinc-500 font-mono">@{u.username}</span>
                    </div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1 text-center">
                  <DashStat label="Reported" value={c.reported} tone={c.reported > 0 ? 'default' : 'default'} />
                  <DashStat label="Fixed"    value={c.fixed} tone={c.fixed > 0 ? 'green' : 'default'} />
                  <DashStat label="TG"       value={u.tgConnected ? 'on' : 'off'} tone={u.tgConnected ? 'green' : 'amber'} />
                </div>
              </Card>
            </button>
          );
        })}
      </div>

      <div className="mt-7">
        <TeamSettings />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
//  NEW ISSUE MODAL
// ─────────────────────────────────────────────────────────────────────────
function NewIssueModal({ open, onClose, onCreate }) {
  const toast = useToast();
  const [severity, setSeverity] = useState('major');
  const [title, setTitle] = useState('');
  const [steps, setSteps] = useState(['', '']);
  const [labels, setLabels] = useState([]);

  const create = () => {
    if (!title.trim()) return;
    const id = 'BUG-0' + (50 + Math.floor(Math.random() * 9));
    onCreate && onCreate({ id, title, severity });
    toast({ title: `${id} filed`, body: `Notified triage leads via Telegram`, target: '@sajjad_cto' });
    onClose();
    setTitle(''); setSeverity('major'); setSteps(['','']); setLabels([]);
  };

  return (
    <Dialog open={open} onClose={onClose} width={760}>
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">File new issue</h2>
          <p className="text-[12px] text-zinc-500">Core API · v2.4.1 · as Sajjad <RoleBadge value="cto" /></p>
        </div>
        <button onClick={onClose} className="h-8 w-8 rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center"><Icon name="x" size={16} /></button>
      </div>

      <div className="px-6 py-5 overflow-y-auto space-y-5">
        <div>
          <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Title</label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Concise summary of the bug…" className="h-9 text-[14px]" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Project</label>
            <NativeSelect className="w-full" defaultValue="p1">
              {MOCK_PROJECTS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </NativeSelect>
          </div>
          <div>
            <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Release</label>
            <NativeSelect className="w-full" defaultValue="v2.4.1">
              {MOCK_RELEASES.filter(r => r.status === 'active').map(r => <option key={r.id} value={r.version}>{r.version}</option>)}
            </NativeSelect>
          </div>
        </div>

        <div>
          <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1.5">Severity</label>
          <div className="grid grid-cols-5 gap-1.5">
            {Object.keys(SEVERITY).map(s => (
              <button key={s} onClick={() => setSeverity(s)}
                className={cn('h-9 rounded-md border text-[12.5px] font-medium transition-colors flex items-center justify-center gap-1.5',
                  severity === s
                    ? 'bg-zinc-900 text-white border-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 dark:border-zinc-100'
                    : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50 dark:bg-zinc-950 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900')}>
                <span className={cn('h-1.5 w-1.5 rounded-full', SEVERITY[s].dot)} />
                {SEVERITY[s].label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Description</label>
          <Textarea rows={3} placeholder="What's broken? Paste cURL or stack traces below the description." />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[12px] font-medium text-zinc-700 dark:text-zinc-200">Reproduction steps</label>
            <button onClick={() => setSteps(s => [...s, ''])} className="text-[11.5px] text-blue-600 dark:text-blue-400 inline-flex items-center gap-1"><Icon name="plus" size={11} /> Add step</button>
          </div>
          <div className="space-y-1.5">
            {steps.map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[12px] text-zinc-400 font-mono w-4">{i+1}.</span>
                <Input value={s} onChange={(e) => setSteps(arr => arr.map((x, idx) => idx === i ? e.target.value : x))} placeholder={`Step ${i+1}`} />
                {steps.length > 1 && (
                  <button onClick={() => setSteps(arr => arr.filter((_, idx) => idx !== i))} className="text-zinc-400 hover:text-red-500"><Icon name="x" size={13} /></button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Expected</label>
            <Textarea rows={2} placeholder="What should have happened…" />
          </div>
          <div>
            <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Actual</label>
            <Textarea rows={2} placeholder="What actually happened…" />
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <Field2 label="Browser" placeholder="Chrome 124" />
          <Field2 label="OS" placeholder="macOS 14.4" />
          <Field2 label="Build" placeholder="sha:9a2e1f" mono />
          <Field2 label="Staging" placeholder="staging-2" mono />
        </div>

        <div>
          <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Attachments</label>
          <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 px-6 py-8 text-center text-[12.5px] text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40">
            <Icon name="upload-cloud" size={20} className="mx-auto text-zinc-400 mb-1.5" />
            Drag &amp; drop screenshots, recordings, or logs · or <button className="text-blue-600 dark:text-blue-400">browse</button>
          </div>
        </div>

        <div>
          <label className="block text-[12px] font-medium text-zinc-700 dark:text-zinc-200 mb-1.5">Labels</label>
          <div className="flex flex-wrap gap-1">
            {['wallet','payments','auth','api','ui','reports','notifications'].map(l => (
              <button key={l} onClick={() => setLabels(L => L.includes(l) ? L.filter(x => x !== l) : [...L, l])}
                className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[11.5px]',
                  labels.includes(l)
                    ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                    : 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700')}>{l}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="px-6 py-3 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between bg-zinc-50/60 dark:bg-zinc-900/40">
        <div className="text-[11.5px] text-zinc-500 inline-flex items-center gap-1">
          <Icon name="send" size={11} className="text-blue-500" />
          {severity === 'blocker' || severity === 'critical'
            ? 'Filing as Blocker/Critical will Telegram-notify triage leads immediately'
            : 'Quiet file — won\'t notify until triaged'}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={create} disabled={!title.trim()}><Icon name="plus" size={13} /> File issue</Button>
        </div>
      </div>
    </Dialog>
  );
}

function Field2({ label, placeholder, mono }) {
  return (
    <div>
      <label className="block text-[11px] text-zinc-500 dark:text-zinc-400 mb-1">{label}</label>
      <Input placeholder={placeholder} className={cn(mono && 'font-mono text-[12px]')} />
    </div>
  );
}

Object.assign(window, { SettingsScreen, TeamScreen, NewIssueModal, LabelsSettings });

// ─────────────────────────────────────────────────────────────────────────
//  Labels Settings — admin label management
// ─────────────────────────────────────────────────────────────────────────
const LABEL_COLOR_CHOICES = [
  'bg-zinc-500','bg-red-500','bg-orange-500','bg-amber-500','bg-emerald-500',
  'bg-teal-500','bg-cyan-600','bg-blue-500','bg-indigo-500','bg-violet-500',
  'bg-purple-500','bg-pink-500','bg-fuchsia-500','bg-rose-500',
];

function LabelsSettings() {
  const [labels, setLabels] = useState(MOCK_LABELS);
  const [draft, setDraft] = useState({ name: '', color: 'bg-blue-500', desc: '' });
  const [editId, setEditId] = useState(null);

  const create = () => {
    if (!draft.name.trim()) return;
    setLabels(L => [...L, { id: 'l' + Math.random().toString(36).slice(2,6), ...draft, issueCount: 0 }]);
    setDraft({ name: '', color: 'bg-blue-500', desc: '' });
  };

  return (
    <div className="grid grid-cols-[1fr_320px] gap-5">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{labels.length} labels</h3>
            <p className="text-[12px] text-zinc-500">Used to tag bugs by component, theme, or release area. Edit, rename, or merge.</p>
          </div>
          <Input placeholder="Filter labels…" className="w-[200px]" />
        </div>
        <Card>
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
            {labels.map(l => (
              <li key={l.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className={cn('h-2.5 w-2.5 rounded-full', l.color)} />
                {editId === l.id ? (
                  <input
                    autoFocus
                    defaultValue={l.name}
                    onBlur={(e) => { setLabels(L => L.map(x => x.id === l.id ? { ...x, name: e.target.value } : x)); setEditId(null); }}
                    onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
                    className="h-7 px-1.5 text-[13px] font-medium bg-transparent border border-zinc-300 dark:border-zinc-700 rounded"
                  />
                ) : (
                  <button onClick={() => setEditId(l.id)} className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">{l.name}</button>
                )}
                <span className="text-[12px] text-zinc-500 flex-1 truncate">{l.desc}</span>
                <Badge tone="muted">{l.issueCount} issues</Badge>
                <Dropdown trigger={<Button variant="ghost" size="icon"><Icon name="ellipsis" size={13} /></Button>}>
                  <DropdownItem icon="paint-bucket">Change color</DropdownItem>
                  <DropdownItem icon="pencil" onClick={() => setEditId(l.id)}>Rename</DropdownItem>
                  <DropdownItem icon="merge">Merge into…</DropdownItem>
                  <DropdownSep />
                  <DropdownItem icon="trash-2" danger>Delete</DropdownItem>
                </Dropdown>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Create new label */}
      <Card className="p-4 self-start">
        <CardTitle>New label</CardTitle>
        <CardDesc>Add a component or theme tag.</CardDesc>
        <div className="mt-3 space-y-3">
          <div>
            <label className="block text-[11.5px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Name</label>
            <Input value={draft.name} onChange={(e) => setDraft(d => ({ ...d, name: e.target.value.toLowerCase() }))} placeholder="e.g. websocket" />
          </div>
          <div>
            <label className="block text-[11.5px] font-medium text-zinc-700 dark:text-zinc-200 mb-1">Description (optional)</label>
            <Input value={draft.desc} onChange={(e) => setDraft(d => ({ ...d, desc: e.target.value }))} placeholder="Short description" />
          </div>
          <div>
            <label className="block text-[11.5px] font-medium text-zinc-700 dark:text-zinc-200 mb-1.5">Color</label>
            <div className="flex flex-wrap gap-1.5">
              {LABEL_COLOR_CHOICES.map(c => (
                <button key={c} onClick={() => setDraft(d => ({ ...d, color: c }))}
                  className={cn('h-6 w-6 rounded-md ring-2 ring-offset-1 ring-offset-white dark:ring-offset-zinc-950',
                    c, draft.color === c ? 'ring-zinc-900 dark:ring-zinc-100' : 'ring-transparent')}
                />
              ))}
            </div>
          </div>
          <div className="rounded-md bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 px-3 py-2">
            <div className="text-[10.5px] text-zinc-500 mb-1">Preview</div>
            <span className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11.5px] font-medium bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              <span className={cn('h-1.5 w-1.5 rounded-full', draft.color)} />
              {draft.name || 'label-name'}
            </span>
          </div>
          <Button onClick={create} disabled={!draft.name.trim()} className="w-full"><Icon name="plus" size={12} /> Create label</Button>
        </div>
      </Card>
    </div>
  );
}

function FieldInline({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] text-zinc-500 dark:text-zinc-400 mb-1">{label}</label>
      {children}
    </div>
  );
}
