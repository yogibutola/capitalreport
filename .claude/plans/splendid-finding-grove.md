# Live demo accounts ("Demo" carousel slide)

## Context

The home page hero carousel's third slide ("See It in Action") has a **Demo**
button that currently just links to `/signup` — there is no actual demo. We want
a prospective club or player to click one button and land *inside the real app*
looking at realistic data, without creating an account.

Decisions already made with the user:

- **One-click into a live, pre-seeded demo account** (not a video / tour / screenshot page).
- **Two demos**, surfaced as two buttons that replace the single button on carousel slide 3:
  - **Admin demo** — signs in as a demo *club* (admin) account; showcases league
    management + tournaments.
  - **Player demo** — signs in as a demo *player* account; showcases the player portal.
- **Read-only demo mode** — the backend rejects every write/delete coming from a
  demo session; the frontend hides/disables the primary mutating controls and
  shows a persistent "demo mode" banner. Demo data therefore never degrades, so
  no scheduled reseed is needed — the seed script is run once against each
  environment's Mongo.

## Approach

### 1. Backend — demo session tokens

**`app/utils/security.py`** — no change needed; `create_access_token(data=...)`
already passes arbitrary claims through. Demo tokens will carry `"demo": True`
alongside the usual `sub` / `role`.

**`app/api/v1/routers/pickleball/pb_authorization.py`** — add:

```
POST /api/v1/demo-signin   body: { "persona": "admin" | "player" }
```

Handler calls a new `PBPlayerService.demo_signin(persona)` which:
- maps `persona` → a fixed demo email
  (`demo.club@stackedpaddle.com` / `demo.player@stackedpaddle.com`),
- loads that player via `pb_player_store.find_player_by_email` (404 if the env
  was never seeded — surfaced as a friendly "demo not available" message),
- mints `create_access_token(data={"sub": email, "role": role, "demo": True})`,
- returns the existing **`PlayerResponse`** shape (so the frontend reuses
  `adoptSession`), with a new `is_demo: bool = False` field added to
  `PlayerResponse` in **`app/vo/pb/player.py`** (set `True` here).

Mirror the token/response construction already in
`PBPlayerService.signin_player` ([app/services/pb_player_service.py:50](app/services/pb_player_service.py#L50)) — just skip the password check.

### 2. Backend — enforce read-only for demo sessions

Single choke point: **`app/api/v1/deps.py`**. Every pickleball write route depends
on either `get_current_admin` or `get_current_player` (verified across
[pb_league.py](app/api/v1/routers/pickleball/pb_league.py),
[pb_tournament.py](app/api/v1/routers/pickleball/pb_tournament.py),
[pb_group.py](app/api/v1/routers/pickleball/pb_group.py),
[pb_player.py](app/api/v1/routers/pickleball/pb_player.py)).

Change both deps to also take `request: fastapi.Request` and, when
`payload.get("demo")` is truthy and `request.method` is not a safe method
(`GET` / `HEAD` / `OPTIONS`), raise:

```
HTTPException(403, "This is a read-only demo. Sign up to make changes.")
```

Factor the check into one helper (`_reject_demo_writes(payload, request)`) called
by both deps. This covers profile edit / change-password too (both use
`get_current_player`), which is what we want.

Not covered (acceptable, note only): `POST /tournament/register/public`
([pb_tournament.py:95](app/api/v1/routers/pickleball/pb_tournament.py#L95)) is
unauthenticated by design; a demo visitor gains nothing there they couldn't do
already. Leave it.

### 3. Seed script — `seed_demo.py` (repo root)

New idempotent script next to the existing
[test_data_seeder.py](test_data_seeder.py) /
[test_tournament_seeder.py](test_tournament_seeder.py), reusing their service
wiring (`PBPlayerService`, `PBLeagueService`, `PBTournamentService` + the `pb_*`
stores). It must be safe to re-run (upsert by email / delete-then-recreate the
demo club's league + tournament).

Creates:
- **Demo club admin** `demo.club@stackedpaddle.com` (role `admin`,
  clubName "StackedPaddle Demo Club"), `is_demo` flag on the player doc.
- **Demo player** `demo.player@stackedpaddle.com`, `is_demo` flag.
- **One league** owned by the demo club: ~12 players, several rounds already
  played with scores entered, at least one completed group that has been through
  `process_group_promotion_relegation` — so slotting, standings, and
  promotion/relegation are all visible. Reuse the round/score/slot flow from
  `test_data_seeder.py`.
- **One tournament** owned by the demo club: doubles, DUPR range, a full set of
  registered teams, draw generated. Reuse `test_tournament_seeder.py`.
- The **demo player is a participant** in both the league and the tournament, and
  has completed matches, so the player portal shows upcoming matches, match
  history, and stats.

Run once per environment: `MONGO_URI=... python seed_demo.py` (locally, and once
against the Cloud Run Mongo — via Secret Manager URI — after deploy).

### 4. Frontend — auth service

**`frontend/src/app/auth/auth.ts`**:
- Add `demo?: boolean` to the `User` interface.
- `demoSignin(persona: 'admin' | 'player'): Observable<boolean>` — `POST
  api/v1/demo-signin`, then reuse the existing `adoptSession(...)` logic (extend
  it to copy `is_demo` → `user.demo`).
- `isDemo(): boolean` → `this.currentUser()?.demo === true`.

### 5. Frontend — carousel slide 3

**`frontend/src/app/home/home.ts`** + **`home.html`**:
- Replace the third entry of the `images` array's single CTA with two actions.
  Simplest: keep `images` for the first two slides, special-case the third slide
  in the template (or give the model an optional `actions: {text, handler}[]`).
- `startAdminDemo()` → `demoSignin('admin')` then `router.navigateByUrl('/league')`.
- `startPlayerDemo()` → `demoSignin('player')` then `router.navigateByUrl('/player')`.
- Disable buttons while the request is in flight; on error show the shared toast
  (`FORM_ERROR_UI` / `parseHttpError`, per [frontend-form-error-toolkit](../projects/-Users-yogenderbutola-work-ai-capitalreport/memory/frontend-form-error-toolkit.md)).
- Note the login redirect guard: `LoginComponent` bounces admins out of the
  player login; the demo path bypasses `/login` entirely so that is not an issue,
  but `adminGuard` must accept the demo admin (it checks `role === 'admin'`, which
  the demo admin token has — OK).

### 6. Frontend — read-only affordances

- **Global banner**: a slim fixed bar rendered in
  [frontend/src/app/app.html](frontend/src/app/app.html) when
  `authService.isDemo()` — "You're exploring a read-only demo. [Sign up] to run
  your own league." with a real logout / exit link.
- **Hide/disable primary mutating controls** when `isDemo()`: create-league,
  save-score, run-slotting, create-tournament, generate-draw, delete buttons,
  profile "Save". Search the admin + player components for the buttons that fire
  POST/PUT/DELETE calls and gate them with `*ngIf="!auth.isDemo()"` (or
  `[disabled]`). The backend 403 + toast is the backstop for anything missed —
  the app is zoneless, so the toast callback must run in an injection/zone-safe
  context (see [frontend-is-zoneless](../projects/-Users-yogenderbutola-work-ai-capitalreport/memory/frontend-is-zoneless.md)).

## Critical files

| File | Change |
|------|--------|
| [app/api/v1/routers/pickleball/pb_authorization.py](app/api/v1/routers/pickleball/pb_authorization.py) | new `POST /demo-signin` |
| [app/services/pb_player_service.py](app/services/pb_player_service.py) | new `demo_signin(persona)` |
| [app/vo/pb/player.py](app/vo/pb/player.py) | `PlayerResponse.is_demo` field |
| [app/api/v1/deps.py](app/api/v1/deps.py) | reject non-safe methods for `demo` tokens in both deps |
| `seed_demo.py` (new, repo root) | seed demo club/player/league/tournament |
| [frontend/src/app/auth/auth.ts](frontend/src/app/auth/auth.ts) | `demoSignin`, `isDemo`, `User.demo` |
| [frontend/src/app/home/home.ts](frontend/src/app/home/home.ts) / [home.html](frontend/src/app/home/home.html) | two demo buttons on slide 3 |
| [frontend/src/app/app.html](frontend/src/app/app.html) / [app.ts](frontend/src/app/app.ts) | demo-mode banner |
| admin + player components | hide primary write controls when `isDemo()` |

## Verification

1. **Seed locally**: `export MONGO_URI="mongodb://localhost:27017/?directConnection=true"`,
   `poetry run python seed_demo.py`. Re-run it — confirm no duplicate accounts /
   leagues (idempotent).
2. **Backend tests** (`python -m pytest tests/`):
   - new test: `POST /api/v1/demo-signin {"persona":"admin"}` returns 200, token,
     `is_demo: true`, `role: admin`; `"player"` returns `role: player`.
   - new test: with a demo token, `POST /api/v1/league` and
     `DELETE /api/v1/league/{id}` return 403; a `GET` (e.g. `/api/v1/all_leagues`)
     still returns 200.
   - unknown persona → 422; unseeded env → clean 404/503, not a 500.
3. **Frontend** (`npm run build` — the Vitest suite is known-broken, see
   [frontend-test-suite-broken](../projects/-Users-yogenderbutola-work-ai-capitalreport/memory/frontend-test-suite-broken.md)).
4. **Manual E2E** (`./run_debug.sh` + `cd frontend && npm start`):
   - Home → carousel slide 3 → **Admin demo** → lands on `/league` with the demo
     league + a tournament visible; demo banner shown; "Create league" hidden;
     trying a score edit (if reachable) surfaces the read-only toast.
   - Home → **Player demo** → lands on `/player` with upcoming matches, history,
     and stats populated; profile "Save" disabled.
   - Exit demo via the banner → back to logged-out home.
5. **Deploy**: after `gcloud builds submit --config cloudbuild.yaml`, run
   `seed_demo.py` once against the prod Mongo (URI from Secret Manager).
