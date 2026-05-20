// ─── Shell components: Sidebar, Topbar, Project switcher, AppContext ───────
const AppContext = createContext(null);
function useApp() { return useContext(AppContext); }

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: 'layout-dashboard' },
  { id: 'inbox',     label: 'Inbox',     icon: 'inbox', badgeKey: 'unread' },
  { id: 'issues',    label: 'Issues',    icon: 'bug',
    children: [
      { id: 'issues',   label: 'All Issues' },
      { id: 'triage',   label: 'Triage Queue', badgeKey: 'triage' },
      { id: 'assigned', label: 'My Assigned' },
    ],
  },
  { id: 'releases',    label: 'Releases', icon: 'tag' },
  { id: 'regressions', label: 'Regressions', icon: 'refresh-ccw', badgeKey: 'regressions' },
  { id: 'reports',     label: 'Reports', icon: 'file-bar-chart',
    children: [
      { id: 'release-reports', label: 'Release Reports' },
      { id: 'contributions',   label: 'Contributions' },
    ],
  },
];

const NAV_BOTTOM = [
  { id: 'settings', label: 'Settings', icon: 'settings' },
  { id: 'team',     label: 'Team',     icon: 'users' },
];

function Sidebar({ collapsed, setCollapsed }) {
  const { route, navigate, badges, project, setProject, tweaks, openProfile } = useApp();
  const [openGroup, setOpenGroup] = useState({ issues: true, reports: true });

  const isActive = (id) => route === id;
  const showProjectInSidebar = (tweaks?.projectLocation || 'sidebar') === 'sidebar';

  return (
    <aside
      className={cn(
        'shrink-0 flex flex-col border-r border-zinc-200 bg-white dark:bg-zinc-950 dark:border-zinc-800 transition-[width]',
        collapsed ? 'w-[64px]' : 'w-[244px]',
      )}
    >
      {/* Logo */}
      <div className={cn('flex items-center h-14 px-3 border-b border-zinc-200 dark:border-zinc-800', collapsed && 'justify-center')}>
        <div className="h-7 w-7 rounded-md bg-zinc-900 dark:bg-zinc-100 flex items-center justify-center text-white dark:text-zinc-900">
          <Icon name="radar" size={16} strokeWidth={2.4} />
        </div>
        {!collapsed && (
          <div className="ml-2 flex-1 min-w-0">
            <div className="text-[13px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 leading-none">Releasewatch</div>
            <div className="text-[10px] text-zinc-500 dark:text-zinc-400 mt-0.5">QA · Release health</div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="ml-auto h-7 w-7 rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center"
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          <Icon name={collapsed ? 'chevron-right' : 'chevron-left'} size={14} />
        </button>
      </div>

      {/* Project selector */}
      {!collapsed && showProjectInSidebar && (
        <div className="px-3 py-3 border-b border-zinc-200 dark:border-zinc-800">
          <ProjectSwitcher project={project} setProject={setProject} />
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {NAV.map(item => (
          <NavItem
            key={item.id}
            item={item}
            collapsed={collapsed}
            active={isActive(item.id)}
            openGroup={openGroup}
            setOpenGroup={setOpenGroup}
            navigate={navigate}
            route={route}
            badges={badges}
          />
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-2 pb-3 pt-2 border-t border-zinc-200 dark:border-zinc-800 space-y-0.5">
        {NAV_BOTTOM.map(item => (
          <button
            key={item.id}
            onClick={() => navigate(item.id)}
            className={cn(
              'w-full flex items-center h-8 rounded-md text-sm transition-colors',
              collapsed ? 'justify-center' : 'px-2 gap-2',
              isActive(item.id)
                ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100 font-medium'
                : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800',
            )}
            title={item.label}
          >
            <Icon name={item.icon} size={15} />
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}

        {!collapsed && (
          <button
            onClick={() => openProfile(userById('u7'))}
            className="mt-3 pt-3 border-t border-zinc-200 dark:border-zinc-800 flex items-center gap-2 px-1 -mx-1 w-[calc(100%+8px)] hover:bg-zinc-50 dark:hover:bg-zinc-900 rounded-md transition-colors text-left"
          >
            <Avatar user={userById('u7')} size={26} />
            <div className="min-w-0 flex-1">
              <div className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 truncate">Sajjad</div>
              <div className="text-[10px] text-zinc-500 dark:text-zinc-400">View profile</div>
            </div>
            <span className="h-6 w-6 rounded-md text-zinc-400 flex items-center justify-center">
              <Icon name="chevron-right" size={14} />
            </span>
          </button>
        )}
      </div>
    </aside>
  );
}

function NavItem({ item, collapsed, openGroup, setOpenGroup, navigate, route, badges }) {
  const hasChildren = !!item.children;
  const groupOpen = openGroup[item.id];
  const childActive = hasChildren && item.children.some(c => c.id === route);
  const active = route === item.id || childActive;
  const badge = item.badgeKey ? badges[item.badgeKey] : null;

  if (collapsed) {
    return (
      <button
        onClick={() => navigate(hasChildren ? item.children[0].id : item.id)}
        title={item.label}
        className={cn(
          'w-full flex items-center justify-center h-8 rounded-md transition-colors relative',
          active
            ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100'
            : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800',
        )}
      >
        <Icon name={item.icon} size={15} />
        {badge > 0 && <span className="absolute top-0.5 right-1 h-1.5 w-1.5 rounded-full bg-red-500" />}
      </button>
    );
  }

  return (
    <>
      <button
        onClick={() => hasChildren ? setOpenGroup(g => ({ ...g, [item.id]: !g[item.id] })) : navigate(item.id)}
        className={cn(
          'w-full flex items-center gap-2 h-8 px-2 rounded-md text-sm transition-colors',
          active && !hasChildren
            ? 'bg-zinc-100 text-zinc-900 font-medium dark:bg-zinc-800 dark:text-zinc-100'
            : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800',
        )}
      >
        <Icon name={item.icon} size={15} />
        <span className="flex-1 text-left">{item.label}</span>
        {badge != null && badge > 0 && (
          <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-md bg-zinc-200 px-1 text-[10px] font-semibold text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200">
            {badge}
          </span>
        )}
        {hasChildren && <Icon name={groupOpen ? 'chevron-down' : 'chevron-right'} size={12} className="text-zinc-400" />}
      </button>
      {hasChildren && groupOpen && (
        <div className="pl-7 pb-1 space-y-0.5">
          {item.children.map(c => {
            const cActive = route === c.id;
            const cBadge = c.badgeKey ? badges[c.badgeKey] : null;
            return (
              <button
                key={c.id}
                onClick={() => navigate(c.id)}
                className={cn(
                  'w-full flex items-center gap-2 h-7 px-2 rounded-md text-[13px] transition-colors',
                  cActive
                    ? 'bg-zinc-100 text-zinc-900 font-medium dark:bg-zinc-800 dark:text-zinc-100'
                    : 'text-zinc-500 hover:bg-zinc-50 dark:text-zinc-400 dark:hover:bg-zinc-900',
                )}
              >
                <span className="flex-1 text-left">{c.label}</span>
                {cBadge != null && cBadge > 0 && (
                  <span className="inline-flex h-4 min-w-[18px] items-center justify-center rounded bg-red-500 px-1 text-[10px] font-semibold text-white">
                    {cBadge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}

// ───── Search trigger + Command palette ─────

function SearchTrigger() {
  const { openPalette } = useApp();
  return (
    <button
      onClick={openPalette}
      className="hidden md:flex relative w-[300px] items-center gap-2 h-8 px-2.5 rounded-md border border-zinc-200 bg-zinc-50 dark:bg-zinc-900 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-left"
    >
      <Icon name="search" size={14} className="text-zinc-400" />
      <span className="text-[12.5px] text-zinc-500 dark:text-zinc-400 flex-1 truncate">Search issues, comments, descriptions…</span>
      <kbd className="text-[10px] font-mono text-zinc-400 border border-zinc-200 dark:border-zinc-700 rounded px-1 py-0.5">⌘K</kbd>
    </button>
  );
}

// Lightweight scorer: fulltext + cheap "semantic" by synonym expansion
const SEMANTIC_SYNONYMS = {
  crash: ['error', '500', 'fail', 'fails', 'broken'],
  slow:  ['timeout', 'slow', 'lag', '30s', 'delay'],
  auth:  ['login', 'token', 'session', 'sso', 'authentication'],
  money: ['payment', 'wallet', 'transfer', 'balance', 'transaction'],
  ui:    ['avatar', 'pagination', 'date picker', 'ui', 'layout'],
  push:  ['sms', 'notification', 'push', 'telegram'],
};

function expandQuery(q) {
  const lower = q.toLowerCase().trim();
  const extras = [];
  for (const k of Object.keys(SEMANTIC_SYNONYMS)) {
    if (lower.includes(k)) extras.push(...SEMANTIC_SYNONYMS[k]);
  }
  return [lower, ...extras].filter(Boolean);
}

function scoreIssue(issue, terms) {
  let s = 0;
  const hay = (issue.title + ' ' + issue.id + ' ' + (issue.labels||[]).join(' ')).toLowerCase();
  for (const t of terms) {
    if (!t) continue;
    if (issue.id.toLowerCase() === t) s += 100;
    if (hay.includes(t)) s += 10;
    if (issue.title.toLowerCase().startsWith(t)) s += 6;
  }
  return s;
}

function scoreComment(text, issue, terms) {
  let s = 0;
  const hay = (text || '').toLowerCase();
  for (const t of terms) {
    if (!t) continue;
    if (hay.includes(t)) s += 8;
  }
  return s;
}

function CommandPalette({ open, onClose, onPick }) {
  const { project, navigate } = useApp();
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) { setQ(''); setActive(0); setTimeout(() => inputRef.current?.focus(), 30); }
  }, [open]);

  const results = useMemo(() => {
    const groups = [];
    const projectIssues = MOCK_ISSUES.filter(i => i.projectId === project.id);

    // Always-available commands (no query)
    const commands = [
      { id: 'cmd-new', kind: 'command', title: 'File new issue…', hint: 'Open the new issue form', icon: 'plus', action: () => onPick({ kind: 'command', name: 'new-issue' }) },
      { id: 'cmd-triage', kind: 'command', title: 'Go to triage queue', hint: 'Unassigned issues', icon: 'split', action: () => { navigate('triage'); onClose(); } },
      { id: 'cmd-inbox', kind: 'command', title: 'Open inbox', hint: 'Notifications for me', icon: 'inbox', action: () => { navigate('inbox'); onClose(); } },
      { id: 'cmd-dash', kind: 'command', title: 'Open dashboard', icon: 'layout-dashboard', action: () => { navigate('dashboard'); onClose(); } },
      { id: 'cmd-regr', kind: 'command', title: 'Open regressions', icon: 'refresh-ccw', action: () => { navigate('regressions'); onClose(); } },
      { id: 'cmd-contrib', kind: 'command', title: 'Open contributions report', icon: 'bar-chart-3', action: () => { navigate('contributions'); onClose(); } },
    ];

    if (!q.trim()) {
      groups.push({ label: 'Quick actions', items: commands.slice(0, 6) });
      groups.push({
        label: 'Recent issues',
        items: projectIssues.slice(0, 5).map(i => ({ id: 'iss-' + i.id, kind: 'issue', issue: i, title: i.title, hint: i.id + ' · ' + i.release })),
      });
      return groups;
    }

    const terms = expandQuery(q);
    // Issues
    const issueHits = projectIssues
      .map(i => ({ issue: i, score: scoreIssue(i, terms) }))
      .filter(x => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 6)
      .map(x => ({ id: 'iss-' + x.issue.id, kind: 'issue', issue: x.issue, title: x.issue.title, hint: x.issue.id + ' · ' + x.issue.release, score: x.score }));

    // Comments / descriptions across timelines
    const commentHits = [];
    for (const [bugId, events] of Object.entries(MOCK_TIMELINE)) {
      const issue = projectIssues.find(i => i.id === bugId);
      if (!issue) continue;
      for (const ev of events) {
        if (ev.type !== 'comment') continue;
        const sc = scoreComment(ev.text, issue, terms);
        if (sc > 0) commentHits.push({ id: 'c-' + bugId + '-' + ev.id, kind: 'comment', issue, text: ev.text, actor: ev.actor, time: ev.time, score: sc });
      }
    }
    commentHits.sort((a, b) => b.score - a.score);

    // Members
    const memberHits = MOCK_TEAM.filter(u => (u.name + ' ' + u.username + ' ' + (u.title||'')).toLowerCase().includes(q.toLowerCase()))
      .map(u => ({ id: 'u-' + u.id, kind: 'member', user: u, title: u.name, hint: '@' + u.username + ' · ' + ROLE[u.role]?.label }));

    if (issueHits.length)   groups.push({ label: 'Issues',   items: issueHits });
    if (commentHits.length) groups.push({ label: 'Comments & descriptions · semantic match', items: commentHits.slice(0, 6) });
    if (memberHits.length)  groups.push({ label: 'People', items: memberHits });

    // command matches
    const cmdHits = commands.filter(c => c.title.toLowerCase().includes(q.toLowerCase()));
    if (cmdHits.length) groups.push({ label: 'Commands', items: cmdHits });

    if (groups.length === 0) groups.push({ label: 'No matches', items: [], empty: true });
    return groups;
  }, [q, project, navigate, onClose, onPick]);

  // flatten for keyboard nav
  const flat = useMemo(() => results.flatMap(g => g.items), [results]);
  useEffect(() => { setActive(0); }, [q]);

  const pick = (item) => {
    if (!item) return;
    if (item.kind === 'issue')   { onPick({ kind: 'issue', issue: item.issue }); }
    else if (item.kind === 'comment') { onPick({ kind: 'issue', issue: item.issue }); }
    else if (item.kind === 'member')  { onPick({ kind: 'member', user: item.user }); }
    else if (item.kind === 'command' && item.action) { item.action(); }
  };

  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(a => Math.min(flat.length - 1, a + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(0, a - 1)); }
    else if (e.key === 'Enter')  { e.preventDefault(); pick(flat[active]); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[10vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" />
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-[640px] max-w-[92vw] rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl flex flex-col overflow-hidden"
      >
        <div className="flex items-center gap-2 px-3.5 h-11 border-b border-zinc-200 dark:border-zinc-800">
          <Icon name="search" size={15} className="text-zinc-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKey}
            placeholder="Search across issues, comments, descriptions, people, commands…"
            className="flex-1 bg-transparent text-[14px] outline-none placeholder:text-zinc-400 dark:text-zinc-100"
          />
          <Badge tone="muted">Full-text + semantic</Badge>
          <kbd className="text-[10px] font-mono text-zinc-400 border border-zinc-200 dark:border-zinc-700 rounded px-1 py-0.5">esc</kbd>
        </div>
        <div className="max-h-[60vh] overflow-y-auto py-1">
          {results.map((g, gi) => (
            <div key={gi}>
              <div className="px-3.5 pt-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{g.label}</div>
              {g.empty
                ? <div className="px-3.5 py-4 text-[13px] text-zinc-500">No matches. Try a different keyword.</div>
                : g.items.map((it, idx) => {
                  const fi = flat.indexOf(it);
                  return <PaletteRow key={it.id} item={it} active={fi === active} onMouseEnter={() => setActive(fi)} onClick={() => pick(it)} query={q} />;
                })}
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between px-3.5 h-9 border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 text-[10.5px] text-zinc-500">
          <div className="flex items-center gap-3">
            <span><kbd className="font-mono">↑↓</kbd> navigate</span>
            <span><kbd className="font-mono">↵</kbd> open</span>
            <span><kbd className="font-mono">esc</kbd> close</span>
          </div>
          <div>Scoped to <span className="font-medium text-zinc-700 dark:text-zinc-300">{project.name}</span></div>
        </div>
      </div>
    </div>
  );
}

function PaletteRow({ item, active, onMouseEnter, onClick, query }) {
  const icon =
    item.kind === 'issue'   ? 'bug' :
    item.kind === 'comment' ? 'message-square' :
    item.kind === 'member'  ? 'user' :
    item.icon || 'arrow-right';
  return (
    <button
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3.5 py-2 text-left transition-colors',
        active ? 'bg-zinc-100 dark:bg-zinc-800' : 'hover:bg-zinc-50 dark:hover:bg-zinc-900',
      )}
    >
      <div className={cn('h-7 w-7 rounded-lg flex items-center justify-center shrink-0',
        item.kind === 'issue' && 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300',
        item.kind === 'comment' && 'bg-purple-100 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300',
        item.kind === 'member' && 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300',
        item.kind === 'command' && 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
      )}>
        {item.kind === 'member'
          ? <Avatar user={item.user} size={20} />
          : <Icon name={icon} size={13} />}
      </div>
      <div className="min-w-0 flex-1">
        {item.kind === 'issue' && (
          <>
            <div className="flex items-center gap-2 text-[12px] text-zinc-500">
              <span className="font-mono">{item.issue.id}</span>
              <SeverityBadge value={item.issue.severity} size="sm" />
              <StatusBadge value={item.issue.status} size="sm" />
            </div>
            <div className="text-[13.5px] font-medium text-zinc-900 dark:text-zinc-100 truncate">{highlight(item.issue.title, query)}</div>
          </>
        )}
        {item.kind === 'comment' && (
          <>
            <div className="flex items-center gap-2 text-[12px] text-zinc-500">
              <Avatar user={userById(item.actor)} size={14} />
              <span>{userById(item.actor)?.name}</span>
              <span>on</span>
              <span className="font-mono">{item.issue.id}</span>
            </div>
            <div className="text-[13px] text-zinc-700 dark:text-zinc-200 truncate">{highlight(item.text, query)}</div>
          </>
        )}
        {item.kind === 'member' && (
          <>
            <div className="text-[13.5px] font-medium text-zinc-900 dark:text-zinc-100">{highlight(item.user.name, query)}</div>
            <div className="text-[12px] text-zinc-500">{item.hint}</div>
          </>
        )}
        {item.kind === 'command' && (
          <>
            <div className="text-[13.5px] font-medium text-zinc-900 dark:text-zinc-100">{item.title}</div>
            {item.hint && <div className="text-[12px] text-zinc-500">{item.hint}</div>}
          </>
        )}
      </div>
      <Icon name="corner-down-left" size={12} className={cn('text-zinc-400', !active && 'opacity-0')} />
    </button>
  );
}

function highlight(text, q) {
  if (!q || !q.trim()) return text;
  const lower = text.toLowerCase();
  const needle = q.toLowerCase().trim();
  const i = lower.indexOf(needle);
  if (i < 0) return text;
  return (
    <>{text.slice(0, i)}<mark className="bg-yellow-200 dark:bg-yellow-900/50 dark:text-yellow-200 px-0.5 rounded">{text.slice(i, i + needle.length)}</mark>{text.slice(i + needle.length)}</>
  );
}

function HeaderProjectPill({ project, setProject }) {
  return (
    <Dropdown
      width={260}
      align="left"
      trigger={
        <button className="inline-flex items-center gap-2 h-8 pl-1 pr-2.5 rounded-md border border-zinc-200 bg-white hover:bg-zinc-50 dark:bg-zinc-950 dark:border-zinc-800 dark:hover:bg-zinc-900 transition-colors">
          <div className="h-6 w-6 rounded bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-[11px] font-bold">
            {project.name[0]}
          </div>
          <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{project.name}</span>
          <Icon name="chevrons-up-down" size={12} className="text-zinc-400" />
        </button>
      }
    >
      {({ close }) => (
        <>
          <DropdownLabel>Switch project</DropdownLabel>
          {MOCK_PROJECTS.map(p => (
            <DropdownItem key={p.id} icon={project.id === p.id ? 'check' : 'circle'}
              onClick={() => { setProject(p); close(); }}>
              <div className="flex flex-col">
                <span>{p.name}</span>
                <span className="text-[10px] text-zinc-500">{p.desc}</span>
              </div>
            </DropdownItem>
          ))}
          <DropdownSep />
          <DropdownItem icon="plus">New project…</DropdownItem>
        </>
      )}
    </Dropdown>
  );
}

function HeaderProjectHero({ project, setProject, release, setRelease, releases }) {
  return (
    <div className="flex items-center gap-0 h-9 rounded-lg border border-zinc-200 bg-white dark:bg-zinc-950 dark:border-zinc-800 overflow-hidden">
      <Dropdown
        width={260}
        align="left"
        trigger={
          <button className="flex items-center gap-2 h-full pl-1.5 pr-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors">
            <div className="h-6 w-6 rounded bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-[11px] font-bold">
              {project.name[0]}
            </div>
            <div className="flex flex-col items-start leading-tight">
              <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{project.name}</span>
              <span className="text-[10px] text-zinc-500 -mt-0.5">{project.slug}</span>
            </div>
            <Icon name="chevron-down" size={11} className="text-zinc-400 ml-0.5" />
          </button>
        }
      >
        {({ close }) => (
          <>
            <DropdownLabel>Switch project</DropdownLabel>
            {MOCK_PROJECTS.map(p => (
              <DropdownItem key={p.id} icon={project.id === p.id ? 'check' : 'circle'}
                onClick={() => { setProject(p); close(); }}>
                <div className="flex flex-col">
                  <span>{p.name}</span>
                  <span className="text-[10px] text-zinc-500">{p.desc}</span>
                </div>
              </DropdownItem>
            ))}
          </>
        )}
      </Dropdown>
      <div className="h-5 w-px bg-zinc-200 dark:bg-zinc-800" />
      <Dropdown
        width={200}
        align="left"
        trigger={
          <button className="flex items-center gap-1.5 h-full px-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors">
            <Icon name="tag" size={12} className="text-zinc-400" />
            <span className="font-mono text-[12px] text-zinc-700 dark:text-zinc-200">{release.version}</span>
            <Icon name="chevron-down" size={11} className="text-zinc-400" />
          </button>
        }
      >
        {({ close }) => (
          <>
            <DropdownLabel>Active release</DropdownLabel>
            {releases.map(r => (
              <DropdownItem key={r.id} icon={r.id === release.id ? 'check' : 'circle'}
                onClick={() => { setRelease(r); close(); }}>
                <div className="flex items-center justify-between gap-2 w-full">
                  <span className="font-mono">{r.version}</span>
                  <Badge tone={r.status === 'active' ? 'blue' : 'muted'}>{r.status}</Badge>
                </div>
              </DropdownItem>
            ))}
          </>
        )}
      </Dropdown>
    </div>
  );
}

function ProjectSwitcher({ project, setProject }) {
  return (
    <Dropdown
      width={260}
      align="left"
      trigger={
        <button className="w-full flex items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 hover:bg-zinc-100 dark:bg-zinc-900 dark:border-zinc-800 dark:hover:bg-zinc-800 px-2 py-1.5 text-left transition-colors">
          <div className="h-6 w-6 rounded bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-[11px] font-bold">
            {project.name[0]}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-semibold text-zinc-900 dark:text-zinc-100 truncate">{project.name}</div>
            <div className="text-[10px] text-zinc-500 dark:text-zinc-400">{project.slug}</div>
          </div>
          <Icon name="chevrons-up-down" size={14} className="text-zinc-400" />
        </button>
      }
    >
      {({ close }) => (
        <>
          <DropdownLabel>Switch project</DropdownLabel>
          {MOCK_PROJECTS.map(p => (
            <DropdownItem key={p.id} icon={project.id === p.id ? 'check' : 'circle'}
              onClick={() => { setProject(p); close(); }}>
              <div className="flex flex-col">
                <span>{p.name}</span>
                <span className="text-[10px] text-zinc-500">{p.desc}</span>
              </div>
            </DropdownItem>
          ))}
          <DropdownSep />
          <DropdownItem icon="plus">New project…</DropdownItem>
        </>
      )}
    </Dropdown>
  );
}

// ───── Topbar ─────
function Topbar({ onNewIssue }) {
  const { route, theme, setTheme, role, setRole, project, setProject, release, setRelease, query, setQuery, tweaks, openProfile } = useApp();
  const releasesForProject = MOCK_RELEASES.filter(r => r.projectId === project.id);
  const loc = tweaks?.projectLocation || 'sidebar';

  const crumbs = useMemo(() => {
    const map = {
      dashboard: ['Dashboard'],
      inbox: ['Inbox'],
      issues: ['Issues', 'All Issues'],
      triage: ['Issues', 'Triage Queue'],
      assigned: ['Issues', 'My Assigned'],
      releases: ['Releases'],
      regressions: ['Regressions'],
      'release-reports': ['Reports', 'Release Reports'],
      contributions:    ['Reports', 'Contributions'],
      settings: ['Settings'],
      team: ['Team'],
    };
    return map[route] || ['Dashboard'];
  }, [route]);

  return (
    <header className="sticky top-0 z-20 h-14 shrink-0 border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/80 backdrop-blur flex items-center px-5 gap-3">
      {loc === 'hero' && (
        <HeaderProjectHero project={project} setProject={setProject} release={release} setRelease={setRelease} releases={releasesForProject} />
      )}
      {loc === 'header' && (
        <HeaderProjectPill project={project} setProject={setProject} />
      )}

      {/* Section title (replaces breadcrumbs) */}
      <nav className="flex items-center text-[13px] min-w-0">
        <span className="text-zinc-900 dark:text-zinc-100 font-medium truncate">{crumbs[crumbs.length - 1]}</span>
        {crumbs.length > 1 && <span className="ml-2 text-[11px] text-zinc-400">in {crumbs[0]}</span>}
      </nav>

      <div className="flex-1" />

      {/* Search trigger — opens command palette */}
      <SearchTrigger />

      {/* Release selector (hidden when included in hero) */}
      {loc !== 'hero' && (
      <Dropdown
        width={220}
        trigger={
          <button className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-zinc-200 bg-white text-[12px] font-medium text-zinc-700 hover:bg-zinc-50 dark:bg-zinc-950 dark:border-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-900">
            <Icon name="tag" size={13} />
            <span className="font-mono">{release.version}</span>
            <Icon name="chevron-down" size={12} className="text-zinc-400" />
          </button>
        }
      >
        {({ close }) => (
          <>
            <DropdownLabel>Active release</DropdownLabel>
            {releasesForProject.map(r => (
              <DropdownItem key={r.id} icon={r.id === release.id ? 'check' : 'circle'}
                onClick={() => { setRelease(r); close(); }}>
                <div className="flex items-center justify-between gap-2 w-full">
                  <span className="font-mono">{r.version}</span>
                  <Badge tone={r.status === 'active' ? 'blue' : 'muted'}>{r.status}</Badge>
                </div>
              </DropdownItem>
            ))}
          </>
        )}
      </Dropdown>
      )}

      {/* New issue */}
      <Button variant="default" onClick={onNewIssue}>
        <Icon name="plus" size={14} /> New issue
      </Button>

      {/* Theme */}
      <button
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        className="h-8 w-8 rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center"
        title="Toggle theme"
      >
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={15} />
      </button>

      {/* Self */}
      <button onClick={() => openProfile(userById('u7'))} className="rounded-full hover:ring-2 hover:ring-zinc-300 dark:hover:ring-zinc-700 transition" title="Your profile">
        <Avatar user={userById('u7')} size={28} />
      </button>
    </header>
  );
}

// ─── Reusable rows / chips ───────────────────────────────────────────────

function LabelChip({ children, removable = false, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
      <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
      {children}
      {removable && (
        <button onClick={onRemove} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100">
          <Icon name="x" size={10} />
        </button>
      )}
    </span>
  );
}

function MetricCard({ label, value, sub, tone = 'default', icon, trend }) {
  const tones = {
    default: 'text-zinc-900 dark:text-zinc-100',
    red:     'text-red-600 dark:text-red-400',
    amber:   'text-amber-600 dark:text-amber-400',
    green:   'text-emerald-600 dark:text-emerald-400',
    blue:    'text-blue-600 dark:text-blue-400',
  };
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
        {icon && <Icon name={icon} size={14} className="text-zinc-400" />}
      </div>
      <div className={cn('mt-2 text-3xl font-semibold tabular-nums', tones[tone])}>{value}</div>
      <div className="mt-1 flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400">
        {trend && (
          <span className={cn('inline-flex items-center gap-0.5',
            trend.dir === 'up' ? 'text-emerald-600' : trend.dir === 'down' ? 'text-red-600' : 'text-zinc-500')}>
            <Icon name={trend.dir === 'up' ? 'trending-up' : trend.dir === 'down' ? 'trending-down' : 'minus'} size={11} />
            {trend.value}
          </span>
        )}
        {sub && <span>{sub}</span>}
      </div>
    </Card>
  );
}

// SLA color
function slaColor(hours) {
  if (hours < 4) return { dot: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400' };
  if (hours < 24) return { dot: 'bg-amber-500', text: 'text-amber-600 dark:text-amber-400' };
  return { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400' };
}

Object.assign(window, {
  AppContext, useApp, Sidebar, Topbar, ProjectSwitcher, HeaderProjectPill, HeaderProjectHero,
  LabelChip, MetricCard, slaColor, SearchTrigger, CommandPalette,
});
