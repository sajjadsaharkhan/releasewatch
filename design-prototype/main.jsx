// ─── Main App ───────────────────────────────────────────────────────────────

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "projectLocation": "header"
}/*EDITMODE-END*/;

function parseHash() {
  const h = window.location.hash || '';
  // formats: #/issue/BUG-042  |  #/u/sajjad  |  #/dashboard
  const m = /^#\/?([a-z-]+)(?:\/([^/]+))?/i.exec(h);
  if (!m) return { route: 'dashboard' };
  const r = m[1];
  if (r === 'issue')  return { route: 'issue',  issueId: m[2] };
  if (r === 'u')      return { route: 'profile', username: m[2] };
  return { route: r };
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  const initial = parseHash();
  const [route, setRoute] = useState(initial.route);
  const [selectedIssueId, setSelectedIssueId] = useState(initial.issueId || null);
  const [profileUserId, setProfileUserId] = useState(() => {
    if (initial.username) return userByUsername(initial.username)?.id || 'u7';
    return 'u7';
  });

  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState('light');
  const [role, setRole] = useState('cto');
  const [project, setProject] = useState(MOCK_PROJECTS[0]);
  const [release, setRelease] = useState(MOCK_RELEASES.find(r => r.projectId === project.id && r.status === 'active') || MOCK_RELEASES[0]);
  const [query, setQuery] = useState('');

  const [issues, setIssues] = useState(MOCK_ISSUES);
  const [inbox, setInbox] = useState(MOCK_INBOX);

  const [newIssueOpen, setNewIssueOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Sync hash <-> route
  useEffect(() => {
    let h = '#/' + route;
    if (route === 'issue' && selectedIssueId) h = '#/issue/' + selectedIssueId;
    else if (route === 'profile') {
      const u = userById(profileUserId);
      h = '#/u/' + (u?.username || 'me');
    }
    if (window.location.hash !== h) {
      try { window.history.replaceState(null, '', h); } catch (e) {}
    }
  }, [route, selectedIssueId, profileUserId]);

  useEffect(() => {
    const onHash = () => {
      const p = parseHash();
      setRoute(p.route);
      if (p.issueId) setSelectedIssueId(p.issueId);
      if (p.username) {
        const u = userByUsername(p.username);
        if (u) setProfileUserId(u.id);
      }
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    const r = MOCK_RELEASES.find(r => r.projectId === project.id && r.status === 'active');
    if (r) setRelease(r);
  }, [project.id]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const updateIssue = (next) => setIssues(arr => arr.map(i => i.id === next.id ? next : i));

  const badges = useMemo(() => ({
    unread: inbox.filter(i => !i.read).length,
    triage: issues.filter(i => !i.assignee).length,
    regressions: issues.filter(i => i.regressions > 0).length,
  }), [inbox, issues]);

  const navigate = (r, opts = {}) => {
    setRoute(r);
    if (r === 'issue' && opts.issueId) setSelectedIssueId(opts.issueId);
    if (r === 'profile' && opts.userId) setProfileUserId(opts.userId);
  };

  const openIssue = (issue) => {
    setSelectedIssueId(issue.id);
    setRoute('issue');
  };

  const openProfile = (user) => {
    setProfileUserId(user.id);
    setRoute('profile');
  };

  const openPalette = () => setPaletteOpen(true);
  const closePalette = () => setPaletteOpen(false);

  const onPalettePick = (pick) => {
    if (pick.kind === 'issue')   { openIssue(pick.issue);   closePalette(); }
    else if (pick.kind === 'member')  { openProfile(pick.user); closePalette(); }
    else if (pick.kind === 'command' && pick.name === 'new-issue') { setNewIssueOpen(true); closePalette(); }
  };

  useEffect(() => {
    function handler(e) {
      const inField = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return; }
      if (inField) return;
      if (e.key === 'c' && !e.metaKey && !e.ctrlKey) { setNewIssueOpen(true); }
      if (e.key === '/') { e.preventDefault(); openPalette(); }
      if (e.key === 'Escape' && route === 'issue') { setRoute('issues'); }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [route]);

  const screen = () => {
    switch (route) {
      case 'dashboard':         return <DashboardScreen openIssue={openIssue} />;
      case 'inbox':             return <InboxScreen openIssue={openIssue} />;
      case 'issues':            return <IssuesScreen openIssue={openIssue} view="all" />;
      case 'triage':            return <TriageScreen openIssue={openIssue} />;
      case 'assigned':          return <IssuesScreen openIssue={openIssue} view="assigned" />;
      case 'releases':          return <ReleasesScreen openIssue={openIssue} />;
      case 'regressions':       return <RegressionsScreen openIssue={openIssue} />;
      case 'release-reports':   return <ReleaseReportsScreen />;
      case 'contributions':     return <ContributionsScreen openIssue={openIssue} />;
      case 'settings':          return <SettingsScreen />;
      case 'team':              return <TeamScreen openProfile={openProfile} />;
      case 'profile':           return <ProfileScreen userId={profileUserId} openIssue={openIssue} />;
      case 'issue': {
        const iss = issues.find(i => i.id === selectedIssueId);
        return <IssuePage issue={iss} onClose={() => navigate('issues')} onUpdate={(i) => { updateIssue(i); }} />;
      }
      default: return <DashboardScreen openIssue={openIssue} />;
    }
  };

  return (
    <AppContext.Provider
      value={{
        route, navigate, theme, setTheme, role, setRole,
        project, setProject, release, setRelease, query, setQuery,
        issues, setIssues, updateIssue, inbox, setInbox, badges,
        tweaks: t, openPalette, openIssue, openProfile,
      }}
    >
      <ToastProvider>
        <div className="h-screen w-full flex bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
          <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
          <div className="flex-1 flex flex-col min-w-0 min-h-0">
            <Topbar onNewIssue={() => setNewIssueOpen(true)} />
            <main className="flex-1 min-h-0 overflow-y-auto" data-screen-label={route}>
              {screen()}
            </main>
          </div>

          <CommandPalette open={paletteOpen} onClose={closePalette} onPick={onPalettePick} />
          <NewIssueModal open={newIssueOpen} onClose={() => setNewIssueOpen(false)} onCreate={() => {}} />

          <TweaksPanel title="Tweaks">
            <TweakSection label="Layout" />
            <TweakRadio
              label="Project selector"
              value={t.projectLocation}
              options={[
                { value: 'sidebar', label: 'Sidebar' },
                { value: 'header',  label: 'Header pill' },
                { value: 'hero',    label: 'Hero' },
              ]}
              onChange={(v) => setTweak('projectLocation', v)}
            />
            <div className="text-[10.5px] leading-snug mt-1 px-0.5" style={{ color: 'rgba(41,38,27,.55)' }}>
              Toggle <strong>⌘K</strong> to open the global search palette.
            </div>
          </TweaksPanel>
        </div>
      </ToastProvider>
    </AppContext.Provider>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
