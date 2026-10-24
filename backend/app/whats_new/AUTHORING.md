# Writing a What's new note

A **note** tells Releasewatch's own users what changed in one production deploy. It
opens once per person as the What's new modal and stays in the changelog. Each **highlight**
in it can carry a **tour**: a short guided walk through the feature's whole **journey**,
in the real app.

Every note is written for **teams**:

| Team | Roles |
|---|---|
| `support` | support |
| `tech` | developer, qa, product_manager, cto, admin |

A person sees only the highlights and tours for their team. The modal opens for them only
when the note has something new or improved for their team; a note with nothing for them is
left out of their changelog.

## Steps

1. **Fix the deploy.** Ask the developer for the deploy date unless they gave it. The note
   is `notes/<YYYY-MM-DD>.md` (in this folder); the newest existing file is the previous
   note. Done when you have the date and the previous note's date.

2. **List every change.** Read `git log --oneline` from the previous note's date to the
   deploy, and the slices or tasks it names. Sort each change into a highlight or
   **skipped**: a highlight is anything a person sees or does differently; refactors, tests,
   tooling and dev-only work are skipped. Done when every commit in the range is a highlight
   or a skipped line with its reason.

3. **Give each highlight a kind and teams.**
   - `new` — a capability that didn't exist. `improved` — an existing one works better.
     `fixed` — a bug people hit is gone.
   - Teams come from who reaches the screen: read the role gates (`frontend/src/lib/roles.js`,
     `isSupport` / `TechRoute` in `App.jsx`, `allowed_actions` from `backend/app/policy.py`).
     A change on a screen both teams use gets both.

   Show the developer the list (kind, teams, title per highlight, plus the skipped lines) and
   wait for their go-ahead. Done when they've approved it.

4. **Write the note** in the format below, by the copy rules. Done when every highlight has
   its fields and every team with a highlight has a headline.

5. **Write the tours.** Every `new` and `improved` highlight gets one; `fixed` never does.
   Walk the journey yourself in the running app first (`http://localhost:5173`, signed in as
   a user of that team), then write one step per action or screen, from where a person
   starts to the outcome. Done when each tour covers the whole journey and every anchor it
   uses exists in the code (see Anchors).

6. **Verify.** Run `make test` (the notes test parses every note and checks every anchor),
   then open `http://localhost:5173/?whats-new=replay` once as a `tech` user and once as a
   `support` user, and play **Take the tour** to the end. Done when the test is green and both
   teams' tours run end to end, each step pointing at the right control.

## The note file

YAML front matter, nothing after it.

```markdown
---
date: 2026-10-24
headline:
  tech:
    title: Collapse the sidebar, and more
    summary: More room for boards and a faster way to keep filing.
  support:
    title: Collapse the sidebar
    summary: Shrink the sidebar to icons for more room.
highlights:
  - kind: new
    teams: [tech, support]
    icon: panel-left-close
    title: Collapse the sidebar
    body: Shrink the sidebar to icons with `[` or the button by the logo.
    tour:
      - anchor: sidebar-toggle
        title: Collapse the sidebar
        body: Click here, or press `[` anywhere.
        advance: click
      - anchor: sidebar-nav
        title: Hover for names
        body: Each icon shows its page's name on hover.
      - anchor: sidebar-toggle
        title: Bring it back
        body: Click again, or press `[`, to expand.
        advance: click
  - kind: fixed
    teams: [tech, support]
    title: Editing a comment no longer clears what you typed.
---
```

| Field | Rule |
|---|---|
| `date` | The deploy date; matches the file name. |
| `headline.<team>` | One per team that has a highlight. `title` and `summary` speak only of that team's highlights. |
| `kind` | `new`, `improved` or `fixed`. |
| `teams` | `[tech]`, `[support]` or `[tech, support]`. |
| `icon` | A lucide name in kebab-case that exists in `lucide-react` 0.453. `new` and `improved` only. |
| `title` | The feature or the fix. |
| `body` | One sentence; inline markdown only. `new` and `improved` only. |
| `tour` | The journey's steps, in order. `new` and `improved` only. |

A tour step:

| Field | Rule |
|---|---|
| `anchor` | A `data-tour` id on the control the step points at. |
| `title` | Up to 5 words. |
| `body` | One sentence, up to 15 words. |
| `advance` | `next` (the default: the person clicks Next) or `click` (the step moves on when the person clicks the anchor, doing the step for real). |
| `route` | Optional. The path to open before the step, when the journey starts on another page. |

## Journeys

A tour is the feature's **full journey**: the entry point a person would use, each action in
order, and the outcome they get. Skip nothing between the first click and the result, and add
nothing beside it.

- Use `advance: click` wherever the person performs the action: they learn it by doing it, and
  the next step's anchor (a dialog that opens, a menu, a new screen) is on screen when it
  starts.
- A journey that crosses a commit (Create, Save, Delete, Merge, Send, Ship) ends on that
  button with `advance: next`, saying what it does. Tours change no real data.
- A step's anchor is on screen when the step starts: reached by the step before it, or opened
  by its `route`.

## Anchors

An anchor is a `data-tour="<area>-<thing>"` attribute in kebab-case (`sidebar-toggle`,
`new-issue-submit`, `triage-accept`) on the element itself. Add it to the component when it's
missing, and keep one element per id on screen at a time. Reuse an existing id before adding a
new one: `grep -rn 'data-tour=' frontend/src` lists them.

## Copy

Written for the person using the screen, in English, by `docs/design.md` §11.

- Second person, present tense. Say what they can do now and why it helps, in their words.
- Name controls by their exact label, in bold: Click **New issue**.
- Actions in the imperative: "Click **Copy link**." Outcomes in the present: "The link is on
  your clipboard."
- One idea per sentence, plain words, no adjectives selling the feature.
- Speak in the screen's terms: page names, labels, what they see.
- A fix is the outcome as a sentence: "Editing a comment no longer clears what you typed."
