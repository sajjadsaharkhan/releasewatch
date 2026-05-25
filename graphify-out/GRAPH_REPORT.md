# Graph Report - .  (2026-05-25)

## Corpus Check
- 222 files · ~120,126 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1657 nodes · 4250 edges · 99 communities (77 shown, 22 thin omitted)
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 993 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Issue API & Schemas|Issue API & Schemas]]
- [[_COMMUNITY_Projects & Releases API|Projects & Releases API]]
- [[_COMMUNITY_Attachments & S3 Upload API|Attachments & S3 Upload API]]
- [[_COMMUNITY_Team & User Management API|Team & User Management API]]
- [[_COMMUNITY_Issue UI Components|Issue UI Components]]
- [[_COMMUNITY_App Shell & Team Modals|App Shell & Team Modals]]
- [[_COMMUNITY_Settings API|Settings API]]
- [[_COMMUNITY_Analytics Charts & Data Viz|Analytics Charts & Data Viz]]
- [[_COMMUNITY_Docker Infrastructure|Docker Infrastructure]]
- [[_COMMUNITY_Issue Detail & Comment UI|Issue Detail & Comment UI]]
- [[_COMMUNITY_Date & Reporting UI|Date & Reporting UI]]
- [[_COMMUNITY_Core Type Stubs|Core Type Stubs]]
- [[_COMMUNITY_Project & Release Management UI|Project & Release Management UI]]
- [[_COMMUNITY_Reports API & Service|Reports API & Service]]
- [[_COMMUNITY_Labels API & ORM|Labels API & ORM]]
- [[_COMMUNITY_UI Primitives|UI Primitives]]
- [[_COMMUNITY_UI Component Library|UI Component Library]]
- [[_COMMUNITY_ORM Models|ORM Models]]
- [[_COMMUNITY_Frontend NPM Dependencies|Frontend NPM Dependencies]]
- [[_COMMUNITY_Timeline API|Timeline API]]
- [[_COMMUNITY_Telegram Integration|Telegram Integration]]
- [[_COMMUNITY_App Router & Shell|App Router & Shell]]
- [[_COMMUNITY_Issue Service|Issue Service]]
- [[_COMMUNITY_Inbox Service & Models|Inbox Service & Models]]
- [[_COMMUNITY_Command Palette & Search|Command Palette & Search]]
- [[_COMMUNITY_Mock & Demo Data|Mock & Demo Data]]
- [[_COMMUNITY_Regression Service|Regression Service]]
- [[_COMMUNITY_Auth Core Middleware|Auth Core Middleware]]
- [[_COMMUNITY_Auth API (loginrefresh)|Auth API (login/refresh)]]
- [[_COMMUNITY_App Entry & Tweaks Panel|App Entry & Tweaks Panel]]
- [[_COMMUNITY_Redis Cache Client|Redis Cache Client]]
- [[_COMMUNITY_Inbox API|Inbox API]]
- [[_COMMUNITY_Timeline Service|Timeline Service]]
- [[_COMMUNITY_Settings UI Forms|Settings UI Forms]]
- [[_COMMUNITY_FastAPI App Factory|FastAPI App Factory]]
- [[_COMMUNITY_Triage Board UI|Triage Board UI]]
- [[_COMMUNITY_Seed Data & Misc Models|Seed Data & Misc Models]]
- [[_COMMUNITY_File Upload Client (JS)|File Upload Client (JS)]]
- [[_COMMUNITY_Attachment Processing|Attachment Processing]]
- [[_COMMUNITY_Notification Tasks (Celery)|Notification Tasks (Celery)]]
- [[_COMMUNITY_Search Logic & Synonyms|Search Logic & Synonyms]]
- [[_COMMUNITY_Regression Detection Service|Regression Detection Service]]
- [[_COMMUNITY_WebSocket Endpoints|WebSocket Endpoints]]
- [[_COMMUNITY_Dashboard Screen UI|Dashboard Screen UI]]
- [[_COMMUNITY_App Configuration|App Configuration]]
- [[_COMMUNITY_Release ORM Model|Release ORM Model]]
- [[_COMMUNITY_Timeline Comment UI|Timeline Comment UI]]
- [[_COMMUNITY_DB Session & Engine|DB Session & Engine]]
- [[_COMMUNITY_Profile Page & MetricCard|Profile Page & MetricCard]]
- [[_COMMUNITY_Alembic Migrations Runner|Alembic Migrations Runner]]
- [[_COMMUNITY_Inbox Fan-Out Service|Inbox Fan-Out Service]]
- [[_COMMUNITY_Calendar Widget UI|Calendar Widget UI]]
- [[_COMMUNITY_Admin CLI Scripts|Admin CLI Scripts]]
- [[_COMMUNITY_SQLAlchemy Base & Mixins|SQLAlchemy Base & Mixins]]
- [[_COMMUNITY_Label ORM Model|Label ORM Model]]
- [[_COMMUNITY_Project ORM Model|Project ORM Model]]
- [[_COMMUNITY_Inbox Screen UI|Inbox Screen UI]]
- [[_COMMUNITY_Role-Based Access Control|Role-Based Access Control]]
- [[_COMMUNITY_Password Hashing|Password Hashing]]
- [[_COMMUNITY_Claude Settings (permissions)|Claude Settings (permissions)]]
- [[_COMMUNITY_FastAPI Package Init|FastAPI Package Init]]
- [[_COMMUNITY_Core Infrastructure Init|Core Infrastructure Init]]
- [[_COMMUNITY_DB Package Init|DB Package Init]]
- [[_COMMUNITY_ORM Models Init|ORM Models Init]]
- [[_COMMUNITY_Schemas Package Init|Schemas Package Init]]
- [[_COMMUNITY_Services Package Init|Services Package Init]]
- [[_COMMUNITY_Celery App Factory|Celery App Factory]]
- [[_COMMUNITY_Celery Tasks Init|Celery Tasks Init]]
- [[_COMMUNITY_CORS Origins Parser|CORS Origins Parser]]
- [[_COMMUNITY_Async DB URL|Async DB URL]]
- [[_COMMUNITY_Alembic Sync URL|Alembic Sync URL]]
- [[_COMMUNITY_Project Archived Property|Project Archived Property]]
- [[_COMMUNITY_Description Alias|Description Alias]]
- [[_COMMUNITY_Active Users by Role|Active Users by Role]]
- [[_COMMUNITY_Redis WebSocket Publisher|Redis WebSocket Publisher]]
- [[_COMMUNITY_Issue Fetch or 404|Issue Fetch or 404]]
- [[_COMMUNITY_Common UI Components|Common UI Components]]
- [[_COMMUNITY_Design Tweaks Hook|Design Tweaks Hook]]

## God Nodes (most connected - your core abstractions)
1. `cn()` - 99 edges
2. `TimelineEventType` - 46 edges
3. `IssueTimeline` - 37 edges
4. `Button` - 36 edges
5. `IssueAttachment` - 33 edges
6. `datetime` - 32 edges
7. `IssueCreate` - 31 edges
8. `IssueUpdate` - 31 edges
9. `PresignRequest` - 28 edges
10. `PresignResponse` - 28 edges

## Surprising Connections (you probably didn't know these)
- `Prototype HTML (CDN-based)` --semantically_similar_to--> `Frontend HTML Entry Point`  [INFERRED] [semantically similar]
  prototype/index.html → frontend/index.html
- `TweakColor()` --calls--> `key()`  [INFERRED]
  prototype/tweaks-panel.jsx → frontend/src/lib/markdown.js
- `str` --uses--> `Base`  [INFERRED]
  backend/app/db/models/system_setting.py → backend/app/db/base.py
- `str` --uses--> `Base`  [INFERRED]
  backend/app/db/models/label.py → backend/app/db/base.py
- `str` --uses--> `Base`  [INFERRED]
  backend/app/db/models/project.py → backend/app/db/base.py

## Hyperedges (group relationships)
- **Backend Data Stack (PostgreSQL + Redis + Alembic)** — releasewatch_claude_postgres, releasewatch_claude_redis, releasewatch_claude_alembic, releasewatch_claude_backend_models [INFERRED 0.95]
- **Celery Background Task Stack (Worker + Beat + Redis)** — docker_compose_yml_worker_service, docker_compose_yml_beat_service, docker_compose_yml_redis_service, releasewatch_claude_celery [EXTRACTED 1.00]
- **Frontend API / Mock Data Sync Pattern** — releasewatch_claude_api_js, releasewatch_claude_mockdata, skill_sync_frontend_to_backend [EXTRACTED 0.95]

## Communities (99 total, 22 thin omitted)

### Community 0 - "Issue API & Schemas"
Cohesion: 0.06
Nodes (107): AsyncSession, bool, int, Issue, IssueCreate, IssueSeverity, str, User (+99 more)

### Community 1 - "Projects & Releases API"
Cohesion: 0.07
Nodes (95): AsyncSession, GoNogoRequest, Project, Release, ReleaseCreate, ReleaseResponse, ReleaseUpdate, str (+87 more)

### Community 2 - "Attachments & S3 Upload API"
Cohesion: 0.11
Nodes (76): AttachmentResponse, AsyncSession, Issue, MultipartPartRequest, MultipartPartResponse, MultipartPresignRequest, MultipartPresignResponse, PresignRequest (+68 more)

### Community 3 - "Team & User Management API"
Cohesion: 0.07
Nodes (65): AvatarConfirmRequest, AvatarPresignRequest, AvatarPresignResponse, AsyncSession, User, UUID, AsyncSession, User (+57 more)

### Community 4 - "Issue UI Components"
Cohesion: 0.06
Nodes (39): ChronicRecurrenceTable(), LABEL_COLORS, DraggableIssueCard(), IssueTable(), LabelChip(), LABEL_COLORS, LabelTrendChart(), formatSize() (+31 more)

### Community 5 - "App Shell & Team Modals"
Cohesion: 0.07
Nodes (40): AppContext, api, attachmentsApi, authApi, inboxApi, labelsApi, projectsApi, releasesApi (+32 more)

### Community 6 - "Settings API"
Cohesion: 0.09
Nodes (49): AsyncSession, str, User, str, ConfigurationResponse, GeneralConfig, LLMTestRequest, System-wide configuration setting stored as key-value pairs.      Settings are o (+41 more)

### Community 7 - "Analytics Charts & Data Viz"
Cohesion: 0.06
Nodes (30): LABEL_COLORS, LABEL_NAMES, LABEL_ORDER, LabelBarChart(), MetricChart(), SegmentedBarChart(), SEVERITY_COLORS, SEVERITY_ORDER (+22 more)

### Community 8 - "Docker Infrastructure"
Cohesion: 0.06
Nodes (49): Dev Docker Compose Overrides (hot reload), API Service (docker-compose), Celery Beat Service (docker-compose), Frontend Service (docker-compose), PostgreSQL Service (docker-compose), Redis Service (docker-compose), Celery Worker Service (docker-compose), Frontend HTML Entry Point (+41 more)

### Community 9 - "Issue Detail & Comment UI"
Cohesion: 0.11
Nodes (26): userById(), AttachmentsSection(), CommentComposer(), DescriptionSection(), ENVIRONMENT, highlightCurl(), IssueDetail(), EVENT_ICONS (+18 more)

### Community 10 - "Date & Reporting UI"
Cohesion: 0.10
Nodes (22): COMMON_PRESETS, CustomDateRange(), DateRangeFilter(), MORE_PRESETS, MetricSummaryCard(), TONE_STYLES, ProjectSwitcher(), RegressionFilters() (+14 more)

### Community 11 - "Core Type Stubs"
Cohesion: 0.10
Nodes (22): Any, bool, int, str, bytes, Return a unique S3 object key and a unique ID prefix.          Parameters, Return S3 object tags based on file size for lifecycle policies., Generate a pre-signed POST URL for direct client-side uploads.          Paramete (+14 more)

### Community 12 - "Project & Release Management UI"
Cohesion: 0.12
Nodes (17): MOCK_PROJECTS, ArchiveProjectConfirmModal(), CreateProjectModal(), PROJECT_COLORS, EditProjectModal(), PROJECT_COLORS, CreateReleaseModal(), EditReleaseModal() (+9 more)

### Community 13 - "Reports API & Service"
Cohesion: 0.12
Nodes (27): AsyncSession, int, str, User, Any, AsyncSession, str, UUID (+19 more)

### Community 14 - "Labels API & ORM"
Cohesion: 0.17
Nodes (31): AsyncSession, str, User, UUID, Label, LabelCreate, LabelResponse, LabelUpdate (+23 more)

### Community 15 - "UI Primitives"
Cohesion: 0.11
Nodes (21): TYPE_DESCRIPTIONS, Calendar(), Card(), CardBody(), CardDesc(), CardHeader(), CardTitle(), DatePicker() (+13 more)

### Community 16 - "UI Component Library"
Cohesion: 0.11
Nodes (25): Avatar(), Badge(), Button(), Card(), CardBody(), CardDesc(), CardHeader(), CardTitle() (+17 more)

### Community 17 - "ORM Models"
Cohesion: 0.09
Nodes (22): str, Base, Project-wide declarative base.      All ORM models must inherit from this class, DeclarativeBase, Issue, IssueSeverity, IssueStatus, Issue ORM model — the core entity in Releasewatch. (+14 more)

### Community 18 - "Frontend NPM Dependencies"
Cohesion: 0.07
Nodes (27): dependencies, axios, clsx, @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities, lucide-react, react (+19 more)

### Community 19 - "Timeline API"
Cohesion: 0.20
Nodes (26): AsyncSession, int, User, UUID, Every discrete event that can appear on an issue's timeline., TimelineEventType, Timeline event schemas., Payload for POST /issues/{id}/timeline (manual comments only). (+18 more)

### Community 20 - "Telegram Integration"
Cohesion: 0.11
Nodes (19): AsyncSession, str, Any, AsyncSession, bool, int, str, Telegram bot integration — notifications and link-account flow.  The bot uses `` (+11 more)

### Community 21 - "App Router & Shell"
Cohesion: 0.09
Nodes (21): CommandPalette(), AppProvider(), AppShell(), Sidebar(), Topbar(), AppInner(), ContributionsPage, DashboardPage (+13 more)

### Community 22 - "Issue Service"
Cohesion: 0.20
Nodes (20): AsyncSession, bool, Issue, IssueCreate, IssueSeverity, str, User, UUID (+12 more)

### Community 23 - "Inbox Service & Models"
Cohesion: 0.18
Nodes (23): Any, AsyncSession, Issue, IssueTimeline, str, User, UserRole, InboxEventType (+15 more)

### Community 24 - "Command Palette & Search"
Cohesion: 0.11
Nodes (11): AppContext, CommandPalette(), highlight(), NAV, NAV_BOTTOM, PaletteRow(), SearchTrigger(), SEMANTIC_SYNONYMS (+3 more)

### Community 25 - "Mock & Demo Data"
Cohesion: 0.09
Nodes (19): MOCK_ACTIVITY, MOCK_CONTRIBUTIONS, MOCK_DISCOVERY, MOCK_FIX_SCATTER, MOCK_FRAGILE, MOCK_INBOX, MOCK_ISSUES, MOCK_LABELS (+11 more)

### Community 26 - "Regression Service"
Cohesion: 0.17
Nodes (17): Any, AsyncSession, int, Issue, Release, str, User, UUID (+9 more)

### Community 27 - "Auth Core Middleware"
Cohesion: 0.18
Nodes (18): Any, AsyncSession, str, User, _build_token(), create_access_token(), create_refresh_token(), get_current_user() (+10 more)

### Community 28 - "Auth API (login/refresh)"
Cohesion: 0.13
Nodes (18): AsyncSession, User, LoginRequest, RefreshRequest, TelegramTokenResponse, TokenResponse, UserMeResponse, get_me() (+10 more)

### Community 29 - "App Entry & Tweaks Panel"
Cohesion: 0.11
Nodes (5): App(), parseHash(), TWEAK_DEFAULTS, TweakColor(), useTweaks()

### Community 30 - "Redis Cache Client"
Cohesion: 0.18
Nodes (17): Any, int, str, delete_cached(), get_cached(), get_redis(), get_redis_raw(), publish() (+9 more)

### Community 31 - "Inbox API"
Cohesion: 0.16
Nodes (17): AsyncSession, bool, int, User, UUID, InboxItemResponse, InboxListResponse, UnreadCountResponse (+9 more)

### Community 32 - "Timeline Service"
Cohesion: 0.16
Nodes (13): Any, AsyncSession, bool, int, IssueTimeline, str, User, UUID (+5 more)

### Community 34 - "FastAPI App Factory"
Cohesion: 0.15
Nodes (13): create_app(), lifespan(), Releasewatch FastAPI application entry-point.  Call ``create_app()`` to get a co, Manage startup and shutdown side-effects., Construct and configure the FastAPI application., close_redis(), init_redis(), Create the Redis connection pool.      Called once during application lifespan s (+5 more)

### Community 35 - "Triage Board UI"
Cohesion: 0.15
Nodes (11): DroppableColumn(), FilterDropdown(), COLUMNS, IssueBoard(), MultiSelectFilterDropdown(), STATUS, SEV_OPTIONS, SORT_OPTIONS (+3 more)

### Community 36 - "Seed Data & Misc Models"
Cohesion: 0.15
Nodes (10): AsyncSession, AWS S3 / MinIO integration — pre-signed URLs, upload validation, lifecycle polic, datetime, RegressionHistory ORM model — tracks each time an issue regresses., SystemSetting ORM model — stores key-value configuration settings., createdAt(), targetDate(), main() (+2 more)

### Community 37 - "File Upload Client (JS)"
Cohesion: 0.24
Nodes (11): preUploadApi, formatFileSize(), uploadAttachment(), uploadAvatar(), uploadIssueAttachment(), uploadMultipart(), uploadPartToS3(), uploadPendingMultipart() (+3 more)

### Community 38 - "Attachment Processing"
Cohesion: 0.24
Nodes (13): int, str, _delete_attachment(), _generate_thumbnail(), Celery tasks — post-upload attachment validation and thumbnail generation.  Afte, Download the image, generate a thumbnail, and upload it back to S3., Remove both the S3 object and the DB row for an invalid attachment., Update file_size_bytes and mime_type on the IssueAttachment row. (+5 more)

### Community 39 - "Notification Tasks (Celery)"
Cohesion: 0.20
Nodes (12): Any, bool, int, str, Task, _AsyncTask, bulk_notify_team(), Celery tasks — Telegram notification delivery with retry logic.  Tasks are enque (+4 more)

### Community 40 - "Search Logic & Synonyms"
Cohesion: 0.22
Nodes (6): PAGES, SYNONYMS, useApp(), MOCK_INBOX, MOCK_ISSUES, NavItem()

### Community 41 - "Regression Detection Service"
Cohesion: 0.29
Nodes (11): Any, str, detect_regression_patterns(), _detect_regressions_async(), _invalidate_async(), invalidate_report_cache(), Celery tasks — report cache invalidation and nightly regression analysis., Invalidate Redis cache keys for the given release reports.      Called whenever (+3 more)

### Community 42 - "WebSocket Endpoints"
Cohesion: 0.29
Nodes (11): str, _authenticate_ws(), WebSocket endpoints — live dashboard events, inbox push, and upload progress., Bidirectional upload progress tracking.      Clients can:     1. Subscribe to pr, Validate JWT from query param. Returns user_id string or None on failure., Live dashboard feed: new issues, status changes, blocker flags (all projects)., Live inbox push — new inbox items for the authenticated user.      Redis channel, ws_dashboard() (+3 more)

### Community 44 - "App Configuration"
Cohesion: 0.24
Nodes (10): database_url(), get_settings(), parse_allowed_origins(), Application configuration via pydantic-settings.  All values can be supplied thr, Return cached Settings instance (singleton via lru_cache)., Central settings object — instantiated once at module level., Settings, sync_database_url() (+2 more)

### Community 45 - "Release ORM Model"
Cohesion: 0.27
Nodes (10): int, str, UUID, blockers(), fixedIssues(), goNoGo(), goNoGoBy(), openIssues() (+2 more)

### Community 46 - "Timeline Comment UI"
Cohesion: 0.27
Nodes (7): CommentItem(), eventText(), inlineMd(), MarkdownPreview(), relTime(), renderCommentBody(), TimelineEvent()

### Community 47 - "DB Session & Engine"
Cohesion: 0.20
Nodes (9): AsyncEngine, AsyncSession, get_db(), get_engine(), init_engine(), Async SQLAlchemy engine and session management.  Usage ----- In FastAPI route ha, Create the async engine and session factory.      Called once during application, Return the module-level async engine (must be initialised first). (+1 more)

### Community 48 - "Profile Page & MetricCard"
Cohesion: 0.27
Nodes (7): MetricCard(), toneMap, userByUsername(), generateActivity(), hexToRgba(), ProfilePage(), SEV_COLORS

### Community 49 - "Alembic Migrations Runner"
Cohesion: 0.25
Nodes (8): do_run_migrations(), Alembic environment — async SQLAlchemy + asyncpg., Run migrations in 'offline' mode.      This configures the context with just a U, Create an async engine and associate a connection with the context., run_async_migrations(), run_migrations_offline(), run_migrations_online(), Connection

### Community 52 - "Inbox Fan-Out Service"
Cohesion: 0.36
Nodes (7): Any, str, _fan_out_async(), fan_out_inbox(), Celery tasks — async fan-out of inbox items.  Rather than performing database fa, Create per-user ``InboxItem`` rows for a triggered event.      Parameters     --, Internal async implementation — opens a fresh DB session.

### Community 53 - "Calendar Widget UI"
Cohesion: 0.33
Nodes (4): isSameDay(), isToday(), MONTHS, WEEKDAYS

### Community 54 - "Admin CLI Scripts"
Cohesion: 0.33
Nodes (6): str, create_admin_user(), get_password_hash(), Create root admin user.  Usage:     python -m scripts.create_admin           # f, Return a bcrypt hash of the plain-text password., Create the root admin user if it doesn't exist.

### Community 55 - "SQLAlchemy Base & Mixins"
Cohesion: 0.33
Nodes (5): SQLAlchemy async declarative base and shared mixins., Mixin that adds ``created_at``, ``updated_at``, and ``deleted_at`` columns., Mixin that adds a server-generated UUID primary key., TimestampMixin, UUIDPrimaryKeyMixin

### Community 56 - "Label ORM Model"
Cohesion: 0.33
Nodes (4): str, Label, Label ORM model — predefined categories for tagging issues., A predefined label that can be applied to issues.      Labels provide a way to c

### Community 57 - "Project ORM Model"
Cohesion: 0.40
Nodes (3): str, Project, A product / application being tracked in Releasewatch.      Each project owns it

### Community 66 - "Role-Based Access Control"
Cohesion: 0.67
Nodes (3): UserRole, Dependency factory — restrict access to users with one of the given roles., require_role()

### Community 67 - "Password Hashing"
Cohesion: 0.67
Nodes (3): bool, Return ``True`` if ``plain_password`` matches the stored bcrypt hash., verify_password()

## Knowledge Gaps
- **162 isolated node(s):** `name`, `version`, `private`, `type`, `dev` (+157 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `datetime` connect `Seed Data & Misc Models` to `Issue API & Schemas`, `Projects & Releases API`, `Attachments & S3 Upload API`, `Team & User Management API`, `Release ORM Model`, `Labels API & ORM`, `Reports API & Service`, `ORM Models`, `Timeline API`, `Telegram Integration`, `Inbox Service & Models`, `Issue Service`, `SQLAlchemy Base & Mixins`, `Label ORM Model`, `Project ORM Model`, `Auth Core Middleware`, `Auth API (login/refresh)`, `Inbox API`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `FastAPI` connect `FastAPI App Factory` to `Issue API & Schemas`, `Projects & Releases API`, `Attachments & S3 Upload API`, `Team & User Management API`, `Timeline Service`, `Settings API`, `WebSocket Endpoints`, `Reports API & Service`, `Labels API & ORM`, `Timeline API`, `Telegram Integration`, `Issue Service`, `Auth Core Middleware`, `Auth API (login/refresh)`, `Inbox API`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `Base` connect `ORM Models` to `Attachments & S3 Upload API`, `Settings API`, `Alembic Migrations Runner`, `Timeline API`, `Inbox Service & Models`, `SQLAlchemy Base & Mixins`, `Label ORM Model`, `Project ORM Model`, `Regression Service`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 43 inferred relationships involving `TimelineEventType` (e.g. with `TimelineEventCreate` and `TimelineEventUpdate`) actually correct?**
  _`TimelineEventType` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `IssueTimeline` (e.g. with `Base` and `str`) actually correct?**
  _`IssueTimeline` has 34 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _507 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Issue API & Schemas` be split into smaller, more focused modules?**
  _Cohesion score 0.06177606177606178 - nodes in this community are weakly interconnected._