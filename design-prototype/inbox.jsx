// ─── Simplified Inbox — single-row mentions list ───────────────────────────

const INBOX_TYPE = {
  assigned:   { icon: 'user-plus',  color: 'text-zinc-600 dark:text-zinc-300',         label: 'assigned this to you' },
  fix_ready:  { icon: 'check',      color: 'text-emerald-600 dark:text-emerald-400',   label: 'marked Fixed — please verify' },
  comment:    { icon: 'message-square', color: 'text-blue-600 dark:text-blue-400',     label: 'commented on' },
  mention:    { icon: 'at-sign',    color: 'text-purple-600 dark:text-purple-400',     label: 'mentioned you' },
  regression: { icon: 'refresh-ccw', color: 'text-red-600 dark:text-red-400',          label: 'flagged a regression' },
};

function InboxScreen({ openIssue }) {
  const { inbox, setInbox } = useApp();
  const [filter, setFilter] = useState('all');

  const filtered = useMemo(() => {
    if (filter === 'unread') return inbox.filter(i => !i.read);
    if (filter === 'mentions') return inbox.filter(i => i.type === 'mention' || i.type === 'comment');
    if (filter === 'assigned') return inbox.filter(i => i.type === 'assigned' || i.type === 'fix_ready');
    return inbox;
  }, [inbox, filter]);

  const markAllRead = () => setInbox(prev => prev.map(i => ({ ...i, read: true })));
  const unread = inbox.filter(i => !i.read).length;

  const openItem = (item) => {
    setInbox(prev => prev.map(i => i.id === item.id ? { ...i, read: true } : i));
    const issue = MOCK_ISSUES.find(i => i.id === item.issueId);
    if (issue) openIssue(issue);
  };

  return (
    <div className="px-7 py-6 max-w-3xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-end justify-between mb-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Inbox</div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">{unread} unread</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Where you were mentioned, assigned, or your fixes are waiting.</p>
        </div>
        <Button variant="outline" size="sm" onClick={markAllRead}>
          <Icon name="check-check" size={12} /> Mark all read
        </Button>
      </div>

      {/* Filter */}
      <div className="mb-3">
        <Tabs
          value={filter}
          onValueChange={setFilter}
          options={[
            { value: 'all',      label: 'All',      badge: inbox.length },
            { value: 'unread',   label: 'Unread',   badge: unread },
            { value: 'mentions', label: 'Mentions' },
            { value: 'assigned', label: 'Assigned' },
          ]}
        />
      </div>

      {/* Simple list */}
      <Card className="overflow-hidden">
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
          {filtered.length === 0 && (
            <li><Empty icon="check-check" title="All caught up" body="Nothing to read." /></li>
          )}
          {filtered.map(item => {
            const actor = userById(item.actor);
            const t = INBOX_TYPE[item.type] || INBOX_TYPE.comment;
            return (
              <li key={item.id}>
                <button
                  onClick={() => openItem(item)}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors',
                    !item.read && 'bg-blue-50/30 dark:bg-blue-950/15',
                  )}
                >
                  {/* unread dot */}
                  <span className={cn('h-2 w-2 rounded-full shrink-0', !item.read ? 'bg-blue-500' : 'bg-transparent')} />

                  {/* actor avatar */}
                  {actor
                    ? <Avatar user={actor} size={28} />
                    : <div className="h-7 w-7 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center text-zinc-500"><Icon name="bot" size={12} /></div>}

                  {/* line */}
                  <div className="min-w-0 flex-1 flex items-center gap-1.5 text-[13.5px] leading-snug">
                    <Icon name={t.icon} size={12} className={cn('shrink-0', t.color)} />
                    <span className={cn('font-medium text-zinc-900 dark:text-zinc-100')}>{actor ? actor.name : 'System'}</span>
                    <span className="text-zinc-500 dark:text-zinc-400 truncate">{eventBlurb(item)}</span>
                    <span className="font-mono text-[11.5px] text-blue-600 dark:text-blue-400 shrink-0">{item.issueId}</span>
                  </div>

                  <span className="text-[11px] text-zinc-400 tabular-nums shrink-0">{item.time}</span>
                  <Icon name="chevron-right" size={13} className="text-zinc-300 dark:text-zinc-700 shrink-0" />
                </button>
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="text-[11.5px] text-zinc-500 dark:text-zinc-400 mt-3 inline-flex items-center gap-1.5">
        <Icon name="info" size={11} />
        Notifications also arrive in Telegram. Click any row to jump to the issue.
      </div>
    </div>
  );
}

function eventBlurb(item) {
  switch (item.type) {
    case 'assigned':   return 'assigned this to you on';
    case 'fix_ready':  return 'marked Fixed — verify on';
    case 'mention':    return 'mentioned you on';
    case 'regression': return 'reopened as a regression';
    case 'comment':    return 'commented on';
    default:           return 'updated';
  }
}

Object.assign(window, { InboxScreen });
