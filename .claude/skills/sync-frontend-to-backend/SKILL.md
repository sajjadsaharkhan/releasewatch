---
name: sync-frontend-to-backend
description: Connect frontend pages to backend API - frontend is source of truth, backend syncs to match UI needs
---

You are in **Frontend-First Sync Mode**. The user's development methodology:

1. **Frontend is the source of truth** — UI drives all backend decisions
2. **Never add UI from backend schema** — backend must conform to frontend needs
3. **Remove all mock data** — frontend must use real backend data dynamically
4. **Auto-migrate** — if database is missing fields, add them via Alembic

## Your Workflow

When given a frontend page/component to sync:

### Step 1: Analyze Frontend Data Needs

Read the frontend page and identify:
- All API calls (check `src/lib/api.js` usage)
- Component props and state
- Data fields rendered in the UI
- Form inputs and submissions

### Step 2: Check Backend API Coverage

For each data need from Step 1:
1. Check if `backend/app/api/v1/*.py` has the endpoint
2. Check if `backend/app/schemas/*.py` has the response/request models
3. Check if `backend/app/db/models/*.py` has the table columns

### Step 3: Sync Backend to Frontend

If backend is missing or different:

**API Routes** (`backend/app/api/v1/`):
- Add missing endpoints
- Ensure responses match frontend expectations

**Schemas** (`backend/app/schemas/`):
- Add fields that frontend uses
- Match field names exactly (camelCase in frontend, snake_case in backend is fine, but map correctly)

**Models** (`backend/app/db/models/`):
- Add missing columns
- Use appropriate types (String, Integer, Boolean, DateTime, etc.)
- Add relationships if needed

**Services** (`backend/app/services/`):
- Implement business logic for new endpoints

### Step 4: Generate and Apply Migration

After model changes:
1. Run `make migrate-new` to generate Alembic migration
2. Review the migration file
3. Run `make migrate` to apply to database

### Step 5: Update Frontend to Use Real API

In the frontend page:
- Remove any `mockData` imports/usage
- Replace with `api.js` calls
- Handle loading states
- Handle error states
- Ensure dynamic data rendering

### Step 6: Verify

- Check that frontend loads real data from backend
- Verify no hardcoded or mock data remains
- Test the full flow (list, detail, create, update, delete as applicable)

## Important Rules

- **NEVER** suggest adding frontend components because "backend already has it"
- **ALWAYS** make backend match what frontend expects
- **Field names matter** — if frontend uses `fullName`, backend should provide it (as `full_name`)
- **Ask before running migrations** if it's destructive
- **Show the diff** of what you're changing in backend

## Usage

Invoke via:
```
/skill sync-frontend-to-backend <frontend-page-path>
```

Example:
```
/skill sync-frontend-to-backend frontend/src/pages/TeamPage.jsx
```
