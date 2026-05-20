// ─── Mock data + constants ──────────────────────────────────────────────────

const MOCK_PROJECTS = [
  { id: 'p1', name: 'Core API', slug: 'core-api', desc: 'Backend services, wallet, payments' },
  { id: 'p2', name: 'Mobile App', slug: 'mobile-app', desc: 'iOS + Android consumer app' },
  { id: 'p3', name: 'Admin Panel', slug: 'admin-panel', desc: 'Internal operator tooling' },
];

const MOCK_RELEASES = [
  { id: 'r1', projectId: 'p1', version: 'v2.4.1', status: 'active',   blockers: 2, criticals: 4, total: 18, fixed: 6,  regressionRate: 23, signedOff: false, lastActivity: '4m ago' },
  { id: 'r2', projectId: 'p1', version: 'v2.3.0', status: 'archived', blockers: 0, criticals: 0, total: 24, fixed: 24, regressionRate: 12, signedOff: true,  lastActivity: '12d ago' },
  { id: 'r3', projectId: 'p2', version: 'v1.8.0', status: 'active',   blockers: 0, criticals: 2, total: 9,  fixed: 5,  regressionRate: 11, signedOff: false, lastActivity: '38m ago' },
  { id: 'r4', projectId: 'p2', version: 'v1.7.2', status: 'archived', blockers: 0, criticals: 0, total: 12, fixed: 12, regressionRate: 8,  signedOff: true,  lastActivity: '21d ago' },
  { id: 'r5', projectId: 'p3', version: 'v0.9.1', status: 'active',   blockers: 1, criticals: 1, total: 6,  fixed: 2,  regressionRate: 17, signedOff: false, lastActivity: '2h ago' },
];

const MOCK_TEAM = [
  { id: 'u1', name: 'Maryam K.',  username: 'maryam.k',  initials: 'MK', role: 'qa',        tg: '@maryam_k',   color: 'bg-purple-500',  tgConnected: true,  joinedAt: '2024-08-02', title: 'Senior QA Engineer',   email: 'maryam@releasewatch.dev',  bio: 'Likes finding race conditions. 9 yrs QA.', location: 'Tehran, IR' },
  { id: 'u2', name: 'Sara N.',    username: 'sara.n',    initials: 'SN', role: 'qa',        tg: '@sara_n',     color: 'bg-pink-500',    tgConnected: true,  joinedAt: '2024-09-14', title: 'QA Engineer',          email: 'sara@releasewatch.dev',    bio: 'Payments + APIs. ISTQB.',                  location: 'Tehran, IR' },
  { id: 'u3', name: 'Neda F.',    username: 'neda.f',    initials: 'NF', role: 'qa',        tg: '@neda_f',     color: 'bg-rose-500',    tgConnected: false, joinedAt: '2025-01-10', title: 'Junior QA Engineer',   email: 'neda@releasewatch.dev',    bio: 'Mobile + i18n.',                            location: 'Isfahan, IR' },
  { id: 'u4', name: 'Ali R.',     username: 'ali.r',     initials: 'AR', role: 'developer', tg: '@ali_r',      color: 'bg-blue-500',    tgConnected: true,  joinedAt: '2024-03-22', title: 'Backend Engineer',     email: 'ali@releasewatch.dev',     bio: 'Wallet team. Likes locks.',                location: 'Tehran, IR' },
  { id: 'u5', name: 'Dara M.',    username: 'dara.m',    initials: 'DM', role: 'developer', tg: '@dara_m',     color: 'bg-indigo-500',  tgConnected: true,  joinedAt: '2024-05-11', title: 'Backend Engineer',     email: 'dara@releasewatch.dev',    bio: 'Payments + reports.',                       location: 'Karaj, IR'  },
  { id: 'u6', name: 'Kamran J.',  username: 'kamran.j',  initials: 'KJ', role: 'developer', tg: '@kamran_j',   color: 'bg-cyan-600',    tgConnected: true,  joinedAt: '2024-11-30', title: 'Frontend Engineer',    email: 'kamran@releasewatch.dev',  bio: 'Auth + SSO.',                               location: 'Tehran, IR' },
  { id: 'u7', name: 'Sajjad',     username: 'sajjad',    initials: 'SJ', role: 'cto',       tg: '@sajjad_cto', color: 'bg-amber-500',   tgConnected: true,  joinedAt: '2024-01-04', title: 'CTO',                  email: 'sajjad@releasewatch.dev',  bio: 'Building Releasewatch.',                    location: 'Tehran, IR' },
];

const userById = (id) => MOCK_TEAM.find(u => u.id === id);
const userByUsername = (u) => MOCK_TEAM.find(x => x.username === (u || '').replace(/^@/, ''));

const MOCK_ISSUES = [
  { id: 'BUG-042', title: 'Wallet sync fails on concurrent transactions',     severity: 'blocker',  status: 'regression',   assignee: 'u4', reporter: 'u1', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['wallet','payments'], regressions: 3, age: '2d',  filedAt: '2025-05-18 09:12', updatedAt: '2025-05-19 09:00', fixedAt: null,            timeToFixH: null, mr: '!198', releaseBlocker: true,  env: { browser: 'Chrome 124', os: 'macOS 14.4', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-041', title: 'Payment gateway timeout after 30s',                severity: 'blocker',  status: 'in-progress',  assignee: 'u5', reporter: 'u2', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['payments','api'],     regressions: 2, age: '3d',  filedAt: '2025-05-17 14:00', updatedAt: '2025-05-19 11:00', fixedAt: null,            timeToFixH: null, mr: '!201', releaseBlocker: true,  env: { browser: '—', os: '—', build: 'sha:9a2e1f', stage: 'staging-1' } },
  { id: 'BUG-039', title: 'Auth token not refreshed on session resume',       severity: 'critical', status: 'fixed',        assignee: 'u6', reporter: 'u1', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['auth'],                regressions: 1, age: '5d',  filedAt: '2025-05-15 08:00', updatedAt: '2025-05-19 18:30', fixedAt: '2025-05-19 18:30', timeToFixH: 14,  mr: '!204', releaseBlocker: false, env: { browser: 'Safari 17.4', os: 'iOS 17.4', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-037', title: 'SMS notification silent failure on Iranian nums',  severity: 'critical', status: 'in-progress',  assignee: 'u4', reporter: 'u3', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['notifications'],       regressions: 1, age: '6d',  filedAt: '2025-05-14 10:00', updatedAt: '2025-05-19 16:00', fixedAt: null,            timeToFixH: null, mr: null,   releaseBlocker: false, env: { browser: '—', os: '—', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-035', title: 'Report export crashes on datasets > 10k rows',     severity: 'major',    status: 'verified',     assignee: 'u5', reporter: 'u2', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['reports'],             regressions: 0, age: '8d',  filedAt: '2025-05-12 12:00', updatedAt: '2025-05-17 12:00', fixedAt: '2025-05-17 12:00', timeToFixH: 32,  mr: '!192', releaseBlocker: false, env: { browser: 'Chrome 124', os: 'Windows 11', build: 'sha:8b1d4c', stage: 'staging-1' } },
  { id: 'BUG-033', title: 'Date picker shows wrong timezone (IRST)',          severity: 'major',    status: 'new',          assignee: null, reporter: 'u3', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['ui'],                  regressions: 0, age: '12h', filedAt: '2025-05-20 04:30', updatedAt: '2025-05-20 04:30', fixedAt: null,            timeToFixH: null, mr: null,   releaseBlocker: false, env: { browser: 'Firefox 125', os: 'Ubuntu', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-030', title: 'Wallet balance shows stale data after transfer',   severity: 'critical', status: 'new',          assignee: null, reporter: 'u1', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['wallet'],              regressions: 0, age: '1d',  filedAt: '2025-05-19 13:00', updatedAt: '2025-05-19 13:00', fixedAt: null,            timeToFixH: null, mr: null,   releaseBlocker: false, env: { browser: 'Chrome 124', os: 'macOS 14.4', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-028', title: 'User avatar broken on mobile Safari',              severity: 'minor',    status: 'triaged',      assignee: 'u6', reporter: 'u7', reporterRole: 'cto',       release: 'v2.4.1', projectId: 'p1', labels: ['ui'],                  regressions: 0, age: '2d',  filedAt: '2025-05-18 19:00', updatedAt: '2025-05-19 10:00', fixedAt: null,            timeToFixH: null, mr: null,   releaseBlocker: false, env: { browser: 'Safari 17.4', os: 'iOS 17.4', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-025', title: 'API rate limit not enforced on bulk endpoints',    severity: 'critical', status: 'in-progress',  assignee: 'u4', reporter: 'u4', reporterRole: 'developer', release: 'v2.4.1', projectId: 'p1', labels: ['api','security'],      regressions: 0, age: '4d',  filedAt: '2025-05-16 09:00', updatedAt: '2025-05-19 17:00', fixedAt: null,            timeToFixH: null, mr: '!199', releaseBlocker: false, env: { browser: '—', os: '—', build: 'sha:9a2e1f', stage: 'staging-1' } },
  { id: 'BUG-022', title: 'Pagination breaks on filtered issue list',         severity: 'minor',    status: 'fixed',        assignee: 'u5', reporter: 'u7', reporterRole: 'cto',       release: 'v2.4.1', projectId: 'p1', labels: ['ui'],                  regressions: 0, age: '5d',  filedAt: '2025-05-15 11:00', updatedAt: '2025-05-19 16:00', fixedAt: '2025-05-19 16:00', timeToFixH: 8,   mr: '!195', releaseBlocker: false, env: { browser: 'Chrome 124', os: 'macOS 14.4', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-020', title: 'Login redirect loop after SSO callback',           severity: 'major',    status: 'triaged',      assignee: 'u4', reporter: 'u2', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['auth','sso'],          regressions: 0, age: '6d',  filedAt: '2025-05-14 15:00', updatedAt: '2025-05-19 12:00', fixedAt: null,            timeToFixH: null, mr: null,   releaseBlocker: false, env: { browser: 'Edge 124', os: 'Windows 11', build: 'sha:9a2e1f', stage: 'staging-2' } },
  { id: 'BUG-018', title: 'Push notification badge count off by one',         severity: 'minor',    status: 'new',          assignee: null, reporter: 'u3', reporterRole: 'qa',        release: 'v2.4.1', projectId: 'p1', labels: ['notifications','mobile'], regressions: 0, age: '6h', filedAt: '2025-05-20 10:00', updatedAt: '2025-05-20 10:00', fixedAt: null,            timeToFixH: null, mr: null,   releaseBlocker: false, env: { browser: '—', os: 'iOS 17.4', build: 'sha:9a2e1f', stage: 'staging-2' } },
];

// Sample timeline for BUG-042 (richest case)
const MOCK_TIMELINE = {
  'BUG-042': [
    { id: 't1',  type: 'filed',            actor: 'u1', time: '2025-05-18 09:12', text: 'filed this issue' },
    { id: 't2',  type: 'assigned',         actor: 'u7', time: '2025-05-18 09:45', text: 'assigned to', target: 'u4' },
    { id: 't3',  type: 'severity_changed', actor: 'u7', time: '2025-05-18 09:46', from: 'critical', to: 'blocker' },
    { id: 't4',  type: 'blocker_flagged',  actor: 'u7', time: '2025-05-18 09:47' },
    { id: 't5',  type: 'comment',          actor: 'u4', time: '2025-05-18 10:30', text: 'I can reproduce this. Happens when two requests hit the wallet endpoint within 200ms. Looking into the locking mechanism.' },
    { id: 't6',  type: 'label_added',      actor: 'u4', time: '2025-05-18 10:31', value: 'wallet' },
    { id: 't7',  type: 'comment',          actor: 'u1', time: '2025-05-18 11:00', text: 'Here is the `cURL` that reproduces it consistently. Attaching screenshot of the 500 error response.' },
    { id: 't8',  type: 'comment',          actor: 'u4', time: '2025-05-18 14:20', text: 'Found the issue — missing row-level lock in the transfer service. Applying pessimistic lock now.', internal: true },
    { id: 't9',  type: 'status_changed',   actor: 'u4', time: '2025-05-18 16:00', from: 'in-progress', to: 'fixed' },
    { id: 't10', type: 'fixed',            actor: 'u4', time: '2025-05-18 16:01', mr: '!198' },
    { id: 't11', type: 'comment',          actor: 'u1', time: '2025-05-18 17:30', text: 'Tested on staging. The concurrent case still fails intermittently. Re-opening.' },
    { id: 't12', type: 'regression',       actor: 'u1', time: '2025-05-18 17:31', text: 'fix did not hold — issue reopened in v2.4.1' },
    { id: 't13', type: 'assigned',         actor: 'u7', time: '2025-05-18 17:45', target: 'u4', text: 're-assigned for second fix attempt' },
    { id: 't14', type: 'comment',          actor: 'u4', time: '2025-05-19 09:00', text: 'Investigating deeper. The lock was applied at the service layer but the read is happening before the lock acquires in edge cases.' },
  ],
  'BUG-039': [
    { id: 't1', type: 'filed',          actor: 'u1', time: '2025-05-15 08:00' },
    { id: 't2', type: 'assigned',       actor: 'u7', time: '2025-05-15 09:00', target: 'u6' },
    { id: 't3', type: 'comment',        actor: 'u6', time: '2025-05-16 10:00', text: 'Reproduced. Patch in progress.' },
    { id: 't4', type: 'status_changed', actor: 'u6', time: '2025-05-19 18:00', from: 'in-progress', to: 'fixed' },
    { id: 't5', type: 'fixed',          actor: 'u6', time: '2025-05-19 18:30', mr: '!204' },
  ],
  'BUG-041': [
    { id: 't1', type: 'filed',     actor: 'u2', time: '2025-05-17 14:00' },
    { id: 't2', type: 'assigned',  actor: 'u7', time: '2025-05-17 14:30', target: 'u5' },
    { id: 't3', type: 'comment',   actor: 'u5', time: '2025-05-18 09:00', text: 'Looking into the connection pool config.' },
    { id: 't4', type: 'comment',   actor: 'u2', time: '2025-05-19 11:00', text: '@dara_m any update? This is blocking the release.' },
  ],
};

const MOCK_INBOX = [
  { id: 'i1', issueId: 'BUG-042', type: 'assigned',    read: false, event: 'assigned this to you',                                          actor: 'u7', time: '4m ago',  severity: 'blocker'  },
  { id: 'i2', issueId: 'BUG-039', type: 'fix_ready',   read: false, event: 'marked this as Fixed — please verify',                          actor: 'u6', time: '1h ago',  severity: 'critical' },
  { id: 'i3', issueId: 'BUG-037', type: 'comment',     read: false, event: 'commented: "Can you share the exact request payload?"',         actor: 'u4', time: '2h ago',  severity: 'critical' },
  { id: 'i4', issueId: 'BUG-041', type: 'mention',     read: false, event: 'mentioned you in a comment',                                    actor: 'u2', time: '3h ago',  severity: 'blocker'  },
  { id: 'i5', issueId: 'BUG-030', type: 'regression',  read: true,  event: 'Regression detected — this issue reappeared in v2.4.1',         actor: null, time: '1d ago',  severity: 'critical' },
  { id: 'i6', issueId: 'BUG-028', type: 'comment',     read: true,  event: 'commented: "Still reproducible on iOS 17.4"',                   actor: 'u3', time: '2d ago',  severity: 'minor'    },
  { id: 'i7', issueId: 'BUG-035', type: 'fix_ready',   read: true,  event: 'verified your fix — closing the loop, nice work',               actor: 'u2', time: '3d ago',  severity: 'major'    },
];

const MOCK_ACTIVITY = [
  { id: 'a1', actor: 'u4', verb: 'marked', target: 'BUG-039', extra: 'as Fixed',     type: 'fixed',     time: '4m ago' },
  { id: 'a2', actor: 'u1', verb: 'filed',  target: 'BUG-030', extra: '',             type: 'filed',     time: '12m ago' },
  { id: 'a3', actor: 'u7', verb: 'assigned', target: 'BUG-033', extra: 'to Ali R.', type: 'assigned',  time: '38m ago' },
  { id: 'a4', actor: 'u1', verb: 'reopened', target: 'BUG-042', extra: 'as Regression', type: 'regression', time: '1h ago' },
  { id: 'a5', actor: 'u5', verb: 'commented on', target: 'BUG-041', extra: '', type: 'comment',   time: '2h ago' },
  { id: 'a6', actor: 'u2', verb: 'verified', target: 'BUG-035', extra: 'fix',     type: 'verified',  time: '3h ago' },
  { id: 'a7', actor: 'u7', verb: 'flagged', target: 'BUG-041', extra: 'as blocker', type: 'regression', time: '5h ago' },
  { id: 'a8', actor: 'u3', verb: 'filed',  target: 'BUG-018', extra: '',             type: 'filed',     time: '6h ago' },
  { id: 'a9', actor: 'u6', verb: 'marked', target: 'BUG-022', extra: 'as Fixed',     type: 'fixed',     time: '1d ago' },
];

const MOCK_CONTRIBUTIONS = [
  { memberId: 'u1', reported: 14, fixed: 0,  avgFixH: null, regressionsCaused: 0, fixRate: null,
    repBySev: { blocker: 3, critical: 5, major: 4, minor: 2, enhancement: 0 } },
  { memberId: 'u2', reported: 11, fixed: 0,  avgFixH: null, regressionsCaused: 0, fixRate: null,
    repBySev: { blocker: 2, critical: 3, major: 3, minor: 3, enhancement: 0 } },
  { memberId: 'u3', reported: 8,  fixed: 0,  avgFixH: null, regressionsCaused: 0, fixRate: null,
    repBySev: { blocker: 1, critical: 2, major: 2, minor: 3, enhancement: 0 } },
  { memberId: 'u4', reported: 2,  fixed: 11, avgFixH: 6.2,  regressionsCaused: 2, fixRate: 92,
    repBySev: { blocker: 0, critical: 1, major: 1, minor: 0, enhancement: 0 } },
  { memberId: 'u5', reported: 1,  fixed: 8,  avgFixH: 9.8,  regressionsCaused: 1, fixRate: 88,
    repBySev: { blocker: 0, critical: 0, major: 1, minor: 0, enhancement: 0 } },
  { memberId: 'u6', reported: 0,  fixed: 6,  avgFixH: 14.1, regressionsCaused: 0, fixRate: 100,
    repBySev: { blocker: 0, critical: 0, major: 0, minor: 0, enhancement: 0 } },
  { memberId: 'u7', reported: 3,  fixed: 0,  avgFixH: null, regressionsCaused: 0, fixRate: null,
    repBySev: { blocker: 0, critical: 0, major: 1, minor: 2, enhancement: 0 } },
];

const MOCK_TIME_TO_FIX = [
  { severity: 'blocker',     avgH: 4.2,  medianH: 3.8,  fastestH: 1.1, slowestH: 14 },
  { severity: 'critical',    avgH: 18.6, medianH: 16,   fastestH: 4,   slowestH: 72 },
  { severity: 'major',       avgH: 38,   medianH: 30,   fastestH: 8,   slowestH: 96 },
  { severity: 'minor',       avgH: 124,  medianH: 96,   fastestH: 24,  slowestH: 336 },
  { severity: 'enhancement', avgH: 200,  medianH: 168,  fastestH: 48,  slowestH: 500 },
];

// Scatter: time-to-fix per issue
const MOCK_FIX_SCATTER = [
  { id: 'BUG-039', sev: 'critical',    sevIdx: 3, hours: 14,  fixer: 'Kamran J.' },
  { id: 'BUG-035', sev: 'major',       sevIdx: 2, hours: 32,  fixer: 'Dara M.' },
  { id: 'BUG-022', sev: 'minor',       sevIdx: 1, hours: 8,   fixer: 'Dara M.' },
  { id: 'BUG-019', sev: 'blocker',     sevIdx: 4, hours: 3.8, fixer: 'Ali R.' },
  { id: 'BUG-016', sev: 'blocker',     sevIdx: 4, hours: 1.1, fixer: 'Ali R.' },
  { id: 'BUG-014', sev: 'blocker',     sevIdx: 4, hours: 14,  fixer: 'Ali R.' },
  { id: 'BUG-012', sev: 'critical',    sevIdx: 3, hours: 4,   fixer: 'Dara M.' },
  { id: 'BUG-010', sev: 'critical',    sevIdx: 3, hours: 72,  fixer: 'Ali R.' },
  { id: 'BUG-008', sev: 'critical',    sevIdx: 3, hours: 16,  fixer: 'Kamran J.' },
  { id: 'BUG-006', sev: 'major',       sevIdx: 2, hours: 96,  fixer: 'Dara M.' },
  { id: 'BUG-005', sev: 'minor',       sevIdx: 1, hours: 96,  fixer: 'Dara M.' },
  { id: 'BUG-004', sev: 'minor',       sevIdx: 1, hours: 24,  fixer: 'Kamran J.' },
  { id: 'BUG-003', sev: 'enhancement', sevIdx: 0, hours: 168, fixer: 'Dara M.' },
];

// Regressions: top recurring
const MOCK_RECURRING = [
  { id: 'BUG-042', title: 'Wallet sync fails on concurrent transactions', component: 'wallet',        timesRegressed: 3, firstSeen: 'v2.1', lastSeen: 'v2.4.1', currentStatus: 'regression',
    history: [ { v: 'v2.1', s: 'fixed' }, { v: 'v2.2', s: 'regression' }, { v: 'v2.3', s: 'fixed' }, { v: 'v2.4', s: 'regression' }, { v: 'v2.4.1', s: 'regression' }, { v: 'v2.5', s: '—' } ] },
  { id: 'BUG-041', title: 'Payment gateway timeout after 30s',            component: 'payments',      timesRegressed: 2, firstSeen: 'v2.2', lastSeen: 'v2.4.1', currentStatus: 'in-progress',
    history: [ { v: 'v2.1', s: '—' }, { v: 'v2.2', s: 'fixed' }, { v: 'v2.3', s: 'regression' }, { v: 'v2.4', s: 'fixed' }, { v: 'v2.4.1', s: 'regression' }, { v: 'v2.5', s: '—' } ] },
  { id: 'BUG-039', title: 'Auth token not refreshed on session resume',   component: 'auth',          timesRegressed: 1, firstSeen: 'v2.3', lastSeen: 'v2.4.1', currentStatus: 'fixed',
    history: [ { v: 'v2.1', s: '—' }, { v: 'v2.2', s: '—' }, { v: 'v2.3', s: 'fixed' }, { v: 'v2.4', s: 'regression' }, { v: 'v2.4.1', s: 'fixed' }, { v: 'v2.5', s: '—' } ] },
  { id: 'BUG-037', title: 'SMS notification silent failure',              component: 'notifications', timesRegressed: 1, firstSeen: 'v2.3', lastSeen: 'v2.4.1', currentStatus: 'in-progress',
    history: [ { v: 'v2.1', s: '—' }, { v: 'v2.2', s: '—' }, { v: 'v2.3', s: 'fixed' }, { v: 'v2.4', s: 'regression' }, { v: 'v2.4.1', s: 'open' }, { v: 'v2.5', s: '—' } ] },
];

const MOCK_FRAGILE = [
  { component: 'wallet',        count: 5 },
  { component: 'payments',      count: 4 },
  { component: 'notifications', count: 3 },
  { component: 'auth',          count: 2 },
  { component: 'ui',            count: 2 },
  { component: 'reports',       count: 1 },
  { component: 'api',           count: 1 },
];

// Bug discovery chart series for the current release
const MOCK_DISCOVERY = [
  { day: 'Mon', filed: 4, fixed: 1 },
  { day: 'Tue', filed: 5, fixed: 2 },
  { day: 'Wed', filed: 3, fixed: 3 },
  { day: 'Thu', filed: 6, fixed: 2 },
  { day: 'Fri', filed: 4, fixed: 4 },
  { day: 'Sat', filed: 1, fixed: 1 },
  { day: 'Sun', filed: 2, fixed: 3 },
];

// ───────── Constants / color tokens ─────────

const SEVERITY = {
  blocker:     { label: 'Blocker',     pill: 'bg-red-100 text-red-800 ring-red-200 dark:bg-red-950/60 dark:text-red-300 dark:ring-red-900/60',           dot: 'bg-red-500'    },
  critical:    { label: 'Critical',    pill: 'bg-orange-100 text-orange-800 ring-orange-200 dark:bg-orange-950/60 dark:text-orange-300 dark:ring-orange-900/60', dot: 'bg-orange-500' },
  major:       { label: 'Major',       pill: 'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:ring-amber-900/60',     dot: 'bg-amber-500'  },
  minor:       { label: 'Minor',       pill: 'bg-blue-100 text-blue-800 ring-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:ring-blue-900/60',          dot: 'bg-blue-500'   },
  enhancement: { label: 'Enhancement', pill: 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',               dot: 'bg-zinc-400'   },
};

const STATUS = {
  'new':         { label: 'New',         pill: 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',          dot: 'bg-zinc-400' },
  'triaged':     { label: 'Triaged',     pill: 'bg-blue-100 text-blue-800 ring-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:ring-blue-900/60',     dot: 'bg-blue-500' },
  'in-progress': { label: 'In Progress', pill: 'bg-indigo-100 text-indigo-800 ring-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300 dark:ring-indigo-900/60', dot: 'bg-indigo-500' },
  'fixed':       { label: 'Fixed',       pill: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:ring-emerald-900/60', dot: 'bg-emerald-500' },
  'verified':    { label: 'Verified',    pill: 'bg-green-100 text-green-800 ring-green-200 dark:bg-green-950/60 dark:text-green-300 dark:ring-green-900/60',  dot: 'bg-green-600' },
  'closed':      { label: 'Closed',      pill: 'bg-zinc-100 text-zinc-500 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700',           dot: 'bg-zinc-400' },
  'regression':  { label: 'Regression',  pill: 'bg-red-100 text-red-800 ring-red-200 dark:bg-red-950/60 dark:text-red-300 dark:ring-red-900/60',           dot: 'bg-red-500'  },
};

const ROLE = {
  qa:        { label: 'QA',  pill: 'bg-purple-100 text-purple-800 ring-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:ring-purple-900/60' },
  developer: { label: 'Dev', pill: 'bg-blue-100 text-blue-800 ring-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:ring-blue-900/60' },
  cto:       { label: 'CTO', pill: 'bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:ring-amber-900/60' },
  admin:     { label: 'Admin', pill: 'bg-zinc-200 text-zinc-800 ring-zinc-300 dark:bg-zinc-700 dark:text-zinc-200 dark:ring-zinc-600' },
};

const TIMELINE_COLOR = {
  filed:            'bg-blue-500',
  assigned:         'bg-zinc-400',
  severity_changed: 'bg-amber-500',
  status_changed:   'bg-indigo-500',
  label_added:      'bg-zinc-400',
  label_removed:    'bg-zinc-400',
  fixed:            'bg-emerald-500',
  verified:         'bg-green-600',
  regression:       'bg-red-500',
  blocker_flagged:  'bg-red-600',
  duplicate_linked: 'bg-zinc-400',
};

// Reusable labels managed in admin panel
const MOCK_LABELS = [
  { id: 'l1',  name: 'wallet',        color: 'bg-purple-500',  desc: 'Wallet, balance, transfers',          issueCount: 18 },
  { id: 'l2',  name: 'payments',      color: 'bg-emerald-500', desc: 'Payment gateways, settlements',       issueCount: 14 },
  { id: 'l3',  name: 'auth',          color: 'bg-blue-500',    desc: 'Login, sessions, tokens',             issueCount: 9 },
  { id: 'l4',  name: 'api',           color: 'bg-cyan-600',    desc: 'Public + internal APIs',              issueCount: 11 },
  { id: 'l5',  name: 'ui',            color: 'bg-pink-500',    desc: 'Visual & interaction bugs',           issueCount: 22 },
  { id: 'l6',  name: 'notifications', color: 'bg-amber-500',   desc: 'Push, SMS, email, Telegram',          issueCount: 7  },
  { id: 'l7',  name: 'reports',       color: 'bg-indigo-500',  desc: 'Analytics + exports',                 issueCount: 4  },
  { id: 'l8',  name: 'security',      color: 'bg-red-500',     desc: 'Auth, rate limits, exposure',         issueCount: 3  },
  { id: 'l9',  name: 'mobile',        color: 'bg-fuchsia-500', desc: 'iOS + Android only',                  issueCount: 6  },
  { id: 'l10', name: 'sso',           color: 'bg-violet-500',  desc: 'Single sign-on flows',                issueCount: 2  },
  { id: 'l11', name: 'i18n',          color: 'bg-teal-500',    desc: 'Translations + locale-specific bugs', issueCount: 1  },
];

// Rich vertical regression log for BUG-042 (multiple events per release)
const MOCK_REGRESSION_LOG = {
  'BUG-042': [
    { id: 'rg1',  release: 'v2.1',   kind: 'fixed',      date: '2024-09-12 14:08', actor: 'u4', note: 'Initial fix with optimistic concurrency. Verified by Maryam K.', mr: '!121' },
    { id: 'rg2',  release: 'v2.2',   kind: 'regression', date: '2024-10-30 11:24', actor: 'u1', note: 'Returned during stress test — 200ms parallel writes leak past lock.' },
    { id: 'rg3',  release: 'v2.2',   kind: 'fixed',      date: '2024-11-04 16:50', actor: 'u4', note: 'Switched to pessimistic row lock + idempotency_key dedupe.', mr: '!138' },
    { id: 'rg4',  release: 'v2.3',   kind: 'verified',   date: '2025-02-18 10:00', actor: 'u2', note: 'No reproductions for 8 weeks. Closing the loop.' },
    { id: 'rg5',  release: 'v2.4',   kind: 'regression', date: '2025-04-21 09:11', actor: 'u1', note: 'Wallet rewrite reintroduced read-before-lock window.' },
    { id: 'rg6',  release: 'v2.4',   kind: 'fixed',      date: '2025-04-23 18:02', actor: 'u4', note: 'Reapplied lock at the repo layer.', mr: '!181' },
    { id: 'rg7',  release: 'v2.4.1', kind: 'regression', date: '2025-05-18 17:31', actor: 'u1', note: 'Different code path — batch transfer endpoint missed the lock.' },
    { id: 'rg8',  release: 'v2.4.1', kind: 'in-progress', date: '2025-05-19 09:00', actor: 'u4', note: 'Investigating batch endpoint specifically.', mr: '!198' },
  ],
};

const CURL_SAMPLE = `curl -X POST 'https://api.releasewatch.dev/v2/wallet/transfer' \\
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIs...' \\
  -H 'Content-Type: application/json' \\
  -d '{
    "from": "wallet_acct_8821",
    "to":   "wallet_acct_9302",
    "amount": 12500,
    "currency": "IRR",
    "idempotency_key": "txn_2025-05-18_001"
  }'`;

Object.assign(window, {
  MOCK_PROJECTS, MOCK_RELEASES, MOCK_TEAM, MOCK_ISSUES, MOCK_TIMELINE,
  MOCK_INBOX, MOCK_ACTIVITY, MOCK_CONTRIBUTIONS, MOCK_TIME_TO_FIX,
  MOCK_FIX_SCATTER, MOCK_RECURRING, MOCK_FRAGILE, MOCK_DISCOVERY,
  MOCK_LABELS, MOCK_REGRESSION_LOG,
  SEVERITY, STATUS, ROLE, TIMELINE_COLOR, CURL_SAMPLE,
  userById, userByUsername,
});
