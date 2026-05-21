// ─── Unified issue timeline + comments ──────────────────────────────────────

function eventText(ev) {
  switch (ev.type) {
    case 'filed':
      return <span>filed this issue</span>;
    case 'assigned': {
      const t = userById(ev.target);
      return <span>assigned to <span className="font-medium text-zinc-700 dark:text-zinc-200">{t?.name}</span>{ev.text ? ` · ${ev.text}` : ''}</span>;
    }
    case 'severity_changed':
      return <span>changed severity <SeverityBadge value={ev.from} size="sm" /> <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" /> <SeverityBadge value={ev.to} size="sm" /></span>;
    case 'status_changed':
      return <span>changed status <StatusBadge value={ev.from} size="sm" /> <Icon name="arrow-right" size={11} className="inline mx-0.5 text-zinc-400" /> <StatusBadge value={ev.to} size="sm" /></span>;
    case 'label_added':
      return <span>added label <LabelChip>{ev.value}</LabelChip></span>;
    case 'label_removed':
      return <span>removed label <LabelChip>{ev.value}</LabelChip></span>;
    case 'fixed':
      return <span>marked as Fixed{ev.mr && <> · linked <span className="inline-flex items-center rounded bg-blue-50 dark:bg-blue-950/40 px-1.5 py-0.5 text-[11px] font-mono text-blue-700 dark:text-blue-300">MR {ev.mr}</span></>}</span>;
    case 'verified':
      return <span>verified the fix</span>;
    case 'regression':
      return <span className="text-red-600 dark:text-red-400 font-medium">{ev.text || 'Regression detected — reopened'}</span>;
    case 'blocker_flagged':
      return <span className="text-red-600 dark:text-red-400 font-medium">flagged this as a release blocker</span>;
    case 'duplicate_linked':
      return <span>marked as duplicate of <span className="font-mono text-blue-600 dark:text-blue-400">{ev.target}</span></span>;
    default:
      return <span>{ev.text || ev.type}</span>;
  }
}

function relTime(timeStr) {
  // mock: convert "2025-05-19 09:00" into something like "May 19, 9:00"
  const d = new Date(timeStr.replace(' ', 'T'));
  if (isNaN(d)) return timeStr;
  const opts = { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
  return d.toLocaleString(undefined, opts);
}

function TimelineEvent({ ev }) {
  const actor = userById(ev.actor);
  const dotClass = TIMELINE_COLOR[ev.type] || 'bg-zinc-400';
  const iconForEvent = {
    filed: 'file-plus', assigned: 'user-plus', severity_changed: 'arrow-up-down',
    status_changed: 'git-pull-request', label_added: 'tag', label_removed: 'tag',
    fixed: 'check', verified: 'shield-check', regression: 'refresh-ccw',
    blocker_flagged: 'octagon-alert', duplicate_linked: 'copy',
  }[ev.type] || 'circle';
  return (
    <li className="relative pl-10 pr-2 py-1.5 group rounded hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
      <span className={cn('absolute left-[8px] top-2.5 h-4 w-4 rounded-full ring-4 ring-white dark:ring-zinc-950 flex items-center justify-center text-white', dotClass)}>
        <Icon name={iconForEvent} size={9} strokeWidth={2.6} />
      </span>
      <div className="flex items-baseline gap-1.5 text-[13px] flex-wrap text-zinc-500 dark:text-zinc-400">
        <span className="font-medium text-zinc-700 dark:text-zinc-200">{actor?.name || 'System'}</span>
        {eventText(ev)}
        <span className="text-zinc-400 dark:text-zinc-500 text-[11px] ml-auto">{relTime(ev.time)}</span>
      </div>
    </li>
  );
}

function CommentItem({ ev }) {
  const actor = userById(ev.actor);
  const isInternal = !!ev.internal;
  return (
    <li className="relative pl-10 pr-1 py-2">
      {/* avatar replaces dot for comments */}
      <div className="absolute left-0 top-2">
        <Avatar user={actor} size={30} ring />
      </div>
      <div className={cn(
        'rounded-lg border bg-white dark:bg-zinc-950 px-3.5 py-2.5',
        isInternal
          ? 'border-amber-200 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-900/50'
          : 'border-zinc-200 dark:border-zinc-800',
      )}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{actor?.name}</span>
          <RoleBadge value={actor?.role} />
          {isInternal && (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 dark:text-amber-300">
              <Icon name="lock" size={10} /> Internal note
            </span>
          )}
          <span className="ml-auto text-[11px] text-zinc-400">{relTime(ev.time)}</span>
        </div>
        <div className="text-[13.5px] text-zinc-700 dark:text-zinc-200 leading-relaxed md">
          {renderCommentBody(ev.text)}
        </div>
      </div>
    </li>
  );
}

// Small UI helpers + naive markdown preview
function MdTool({ icon, title, onClick }) {
  return (
    <button onClick={onClick} title={title} className="h-6 w-6 rounded text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 flex items-center justify-center">
      <Icon name={icon} size={12} />
    </button>
  );
}
function MdSep() {
  return <span className="h-4 w-px bg-zinc-200 dark:bg-zinc-700 mx-0.5" />;
}

function MarkdownPreview({ text }) {
  // very naive markdown-to-JSX for preview only
  if (!text) return null;
  const lines = text.split(/\n/);
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      blocks.push(<pre key={blocks.length} className="rounded-md bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-[12px] font-mono whitespace-pre overflow-x-auto">{buf.join('\n')}</pre>);
      continue;
    }
    if (/^> /.test(line)) {
      blocks.push(<blockquote key={blocks.length} className="border-l-2 border-zinc-300 dark:border-zinc-700 pl-3 text-zinc-600 dark:text-zinc-300 italic">{inlineMd(line.replace(/^> /, ''))}</blockquote>);
      i++; continue;
    }
    if (/^(- |\* )/.test(line)) {
      const items = [];
      while (i < lines.length && /^(- |\* )/.test(lines[i])) {
        items.push(lines[i].replace(/^(- |\* )/, ''));
        i++;
      }
      blocks.push(<ul key={blocks.length} className="list-disc pl-5 my-1 space-y-0.5">{items.map((t, k) => <li key={k}>{inlineMd(t)}</li>)}</ul>);
      continue;
    }
    if (/^\d+\. /.test(line)) {
      const items = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\. /, ''));
        i++;
      }
      blocks.push(<ol key={blocks.length} className="list-decimal pl-5 my-1 space-y-0.5">{items.map((t, k) => <li key={k}>{inlineMd(t)}</li>)}</ol>);
      continue;
    }
    if (line.trim() === '') { blocks.push(<div key={blocks.length} className="h-2" />); i++; continue; }
    blocks.push(<p key={blocks.length}>{inlineMd(line)}</p>);
    i++;
  }
  return <>{blocks}</>;
}

function inlineMd(text) {
  // bold **x**, italic _x_, code `x`, strike ~~x~~, links [t](u), mentions @x
  const parts = [];
  const regex = /(\*\*[^*]+\*\*|~~[^~]+~~|`[^`]+`|_[^_]+_|\[[^\]]+\]\([^)]+\)|@[a-zA-Z0-9_.]+)/g;
  let last = 0;
  let m;
  let key = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) parts.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith('~~')) parts.push(<s key={key++}>{tok.slice(2, -2)}</s>);
    else if (tok.startsWith('`')) parts.push(<code key={key++}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith('_')) parts.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    else if (tok.startsWith('[')) {
      const lm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(tok);
      parts.push(<a key={key++} href={lm[2]} target="_blank" rel="noreferrer">{lm[1]}</a>);
    } else if (tok.startsWith('@')) {
      parts.push(<span key={key++} className="inline-flex items-center rounded px-1 py-0 text-[12px] font-medium bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">{tok}</span>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function renderCommentBody(text) {
  if (!text) return null;
  // very light markdown: backticks for inline code, @mentions → blue pill
  const parts = [];
  const regex = /(`[^`]+`|@[a-zA-Z0-9_]+)/g;
  let last = 0;
  let m;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('`')) {
      parts.push(<code key={m.index}>{tok.slice(1, -1)}</code>);
    } else {
      parts.push(<span key={m.index} className="inline-flex items-center rounded px-1 py-0 text-[12px] font-medium bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">{tok}</span>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <p>{parts}</p>;
}

function IssueTimeline({ events, onAddComment }) {
  const [draft, setDraft] = useState('');
  const [internal, setInternal] = useState(false);
  const [tab, setTab] = useState('write'); // write | preview
  const me = userById('u7');
  const taRef = useRef(null);

  const submit = () => {
    if (!draft.trim()) return;
    onAddComment && onAddComment({ text: draft, internal });
    setDraft('');
    setInternal(false);
    setTab('write');
  };

  // Wrap selection with markers (or insert)
  const wrap = (before, after = before, placeholder = '') => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart, end = ta.selectionEnd;
    const sel = draft.slice(start, end) || placeholder;
    const next = draft.slice(0, start) + before + sel + after + draft.slice(end);
    setDraft(next);
    requestAnimationFrame(() => {
      ta.focus();
      const pos = start + before.length + sel.length;
      ta.setSelectionRange(pos, pos);
    });
  };

  const linePrefix = (prefix) => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    // find start of current line
    const lineStart = draft.lastIndexOf('\n', start - 1) + 1;
    const next = draft.slice(0, lineStart) + prefix + draft.slice(lineStart);
    setDraft(next);
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(start + prefix.length, start + prefix.length);
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Activity & comments</h3>
        <button className="inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
          <Icon name="eye-off" size={11} /> Hide events
        </button>
      </div>

      <ol className="relative spine">
        {events.map(ev => (
          ev.type === 'comment'
            ? <CommentItem key={ev.id} ev={ev} />
            : <TimelineEvent key={ev.id} ev={ev} />
        ))}
      </ol>

      {/* Markdown composer */}
      <div className="relative mt-4 pl-10">
        <div className="absolute left-0 top-1">
          <Avatar user={me} size={30} ring />
        </div>
        <div className={cn('rounded-lg border bg-white dark:bg-zinc-950 focus-within:ring-2 focus-within:ring-zinc-900/10 overflow-hidden',
          internal ? 'border-amber-300 bg-amber-50/40 dark:bg-amber-950/20 dark:border-amber-900/60' : 'border-zinc-200 dark:border-zinc-800')}>
          {/* Tabs + toolbar */}
          <div className="flex items-center justify-between px-2 pt-1.5 pb-1 border-b border-zinc-100 dark:border-zinc-800">
            <Tabs
              value={tab}
              onValueChange={setTab}
              options={[
                { value: 'write',   label: 'Write',   icon: 'pencil' },
                { value: 'preview', label: 'Preview', icon: 'eye' },
              ]}
            />
            {tab === 'write' && (
              <div className="flex items-center gap-0.5">
                <MdTool icon="bold"        title="Bold (⌘B)"        onClick={() => wrap('**', '**', 'bold')} />
                <MdTool icon="italic"      title="Italic"           onClick={() => wrap('_', '_', 'italic')} />
                <MdTool icon="strikethrough" title="Strikethrough"   onClick={() => wrap('~~', '~~', 'text')} />
                <MdSep />
                <MdTool icon="link-2"      title="Link"             onClick={() => wrap('[', '](https://)', 'text')} />
                <MdTool icon="code"        title="Inline code"      onClick={() => wrap('`', '`', 'code')} />
                <MdTool icon="code-2"      title="Code block"       onClick={() => wrap('\n```\n', '\n```\n', 'code')} />
                <MdSep />
                <MdTool icon="list"        title="Bulleted list"    onClick={() => linePrefix('- ')} />
                <MdTool icon="list-ordered" title="Numbered list"   onClick={() => linePrefix('1. ')} />
                <MdTool icon="list-checks" title="Task list"        onClick={() => linePrefix('- [ ] ')} />
                <MdTool icon="quote"       title="Quote"            onClick={() => linePrefix('> ')} />
                <MdSep />
                <MdTool icon="at-sign"     title="Mention"          onClick={() => wrap('@', '', 'username')} />
                <MdTool icon="image"       title="Attach image"     onClick={() => wrap('![alt](', ')', 'url')} />
                <MdTool icon="paperclip"   title="Attach file"      onClick={() => {}} />
              </div>
            )}
          </div>

          {/* Body */}
          {tab === 'write' ? (
            <textarea
              ref={taRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); }
                else if ((e.metaKey || e.ctrlKey) && e.key === 'b') { e.preventDefault(); wrap('**','**','bold'); }
                else if ((e.metaKey || e.ctrlKey) && e.key === 'i') { e.preventDefault(); wrap('_','_','italic'); }
                else if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); wrap('[', '](https://)', 'text'); }
              }}
              placeholder={internal ? 'Internal note in markdown — **bold**, `code`, lists…' : 'Comment in markdown. @mention to notify via Telegram.'}
              rows={4}
              className="w-full resize-none bg-transparent border-0 px-3 py-2.5 text-[13.5px] font-mono leading-relaxed focus:outline-none placeholder:text-zinc-400 text-zinc-800 dark:text-zinc-100"
            />
          ) : (
            <div className="px-3 py-3 text-[13.5px] text-zinc-800 dark:text-zinc-100 leading-relaxed md min-h-[100px]">
              {draft.trim() ? <MarkdownPreview text={draft} /> : <span className="text-zinc-400">Nothing to preview yet.</span>}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between px-2 pb-2 pt-1 border-t border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <label className="inline-flex items-center gap-1.5 text-[11px] text-zinc-500 pl-1">
                <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} className="rounded border-zinc-300" />
                Internal note
              </label>
              <a href="https://www.markdownguide.org/basic-syntax/" target="_blank" rel="noreferrer" className="text-[11px] text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 inline-flex items-center gap-1">
                <Icon name="help-circle" size={11} /> Markdown
              </a>
            </div>
            <div className="flex items-center gap-2">
              {draft.includes('@') && (
                <span className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
                  <Icon name="send" size={11} className="text-blue-500" /> Will notify via Telegram
                </span>
              )}
              <Button size="sm" onClick={submit} disabled={!draft.trim()}>
                Comment <kbd className="ml-1 text-[10px] opacity-60">⌘↵</kbd>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { IssueTimeline, TimelineEvent, CommentItem, relTime, renderCommentBody, MarkdownPreview });
