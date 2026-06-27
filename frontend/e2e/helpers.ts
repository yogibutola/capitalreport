import { Page } from '@playwright/test';
import { execSync } from 'child_process';

// ─── Seeder ─────────────────────────────────────────────────────────────────

/**
 * Runs test_data_seeder.py and returns the league name that was created.
 * Output line we parse: "League Name: Pro_20260315164927"
 */
export function runSeeder(): string {
    const output = execSync(
        '/Users/yogenderbutola/work/ai/capitalreport/.venv/bin/python ' +
        '/Users/yogenderbutola/work/ai/capitalreport/test_data_seeder.py',
        { encoding: 'utf-8' }
    );
    const match = output.match(/League Name:\s+(\S+)/);
    if (!match) throw new Error('Could not parse league name from seeder output:\n' + output);
    console.log('[Seeder] Created league:', match[1]);
    return match[1];
}

// ─── Auth helpers ────────────────────────────────────────────────────────────

export async function adminLogin(page: Page, email: string, password: string) {
    await page.goto('/admin/login');
    await page.waitForLoadState('networkidle');
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin', { timeout: 20_000 });
}

export async function playerLogin(page: Page, email: string, password: string) {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/league', { timeout: 20_000 });
}

export async function logout(page: Page) {
    // Clear the Angular auth session and reload so AuthService re-initialises with no user
    await page.evaluate(() => {
        localStorage.removeItem('pickleball_user');
        sessionStorage.clear();
    });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
}

// ─── Player dashboard helpers ─────────────────────────────────────────────────

/**
 * Navigates to /player and selects a league from the sidebar <select> if multiple leagues exist.
 */
export async function selectLeague(page: Page, leagueName: string) {
    // The Angular bootstrap chain is:
    //   page.goto → effect() → fetchLeaguesForPlayer (req 1) → [in callback] fetchLeagueDetailsByName (req 2)
    // waitForLoadState('networkidle') can fire in the microtask gap between req 1 and req 2,
    // so we use waitForResponse to explicitly wait for req 2 instead.
    const initialLeagueResp = page.waitForResponse(
        resp => resp.url().includes('/api/v1/league/name/') && resp.request().method() === 'GET',
        { timeout: 15_000 }
    ).catch(() => null);

    await page.goto('/player');
    await initialLeagueResp; // wait for the initial fetchLeagueDetailsByName

    // Drain any in-flight fallback requests (fetchLeagueDetailsByName fires a second request
    // by ID if the name-based fetch returns 0 matches for the player).
    await page.waitForLoadState('networkidle', { timeout: 10_000 });

    const leagueSelect = page.locator('select.league-select');
    const isVisible = await leagueSelect.isVisible({ timeout: 3_000 }).catch(() => false);
    if (isVisible) {
        // Use the SPECIFIC league name in the URL filter so we don't accidentally catch
        // the fallback request for an older league (which uses the league ID, not name).
        const encodedName = encodeURIComponent(leagueName);
        const leagueResp = page.waitForResponse(
            resp => resp.url().includes(`/api/v1/league/name/${encodedName}`) && resp.request().method() === 'GET',
            { timeout: 10_000 }
        ).catch(() => null);
        await page.selectOption('select.league-select', { label: leagueName });
        await leagueResp;
        // Drain any fallback request for the test league (triggered if player has no matches in it yet)
        await page.waitForLoadState('networkidle', { timeout: 10_000 });
    }
    await page.waitForTimeout(300); // let Angular flush signals to the DOM
}

// ─── API-based score helpers ──────────────────────────────────────────────────

/**
 * Submits scores for all pending matches in a given round directly via the REST API.
 * The caller must already be logged in (admin or player token in localStorage).
 * This bypasses the Angular frontend, which is unreliable for setup steps due to
 * multi-league signal state and NgZone timing issues.
 *
 * The last match submission synchronously triggers check_group_completion → auto-slotting
 * on the backend, so the next round's matches are ready before this function returns.
 */
export async function submitAllMatchScoresViaApi(
    page: Page,
    leagueName: string,
    roundId: number
): Promise<void> {
    const token = await page.evaluate(() => {
        const u = JSON.parse(localStorage.getItem('pickleball_user') || '{}');
        return (u as any).token || '';
    });

    const leagueData = await page.evaluate(async ({ name, tok }: { name: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/name/${encodeURIComponent(name)}`, {
            headers: { Authorization: `Bearer ${tok}` }
        });
        const d = await res.json();
        return { leagueId: d.league_id as string, matches: (d.matches || []) as any[] };
    }, { name: leagueName, tok: token });

    const pending = leagueData.matches.filter(
        (m: any) => Number(m.round_id) === roundId && m.match_status !== 'completed'
    );
    console.log(`[apiScores] Round ${roundId}: ${leagueData.matches.filter((m:any) => Number(m.round_id) === roundId).length} total, ${pending.length} pending`);

    let scoreIdx = 0;
    for (const match of pending) {
        const s1 = 11;
        const s2 = scoreIdx % 2 === 0 ? 7 : 5;
        scoreIdx++;
        const status = await page.evaluate(
            async ({ tok, payload }: { tok: string; payload: any }) => {
                const r = await fetch('/api/v1/league/match/score', {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                return r.status;
            },
            {
                tok: token,
                payload: {
                    league_id: leagueData.leagueId,
                    match_id: match.match_id,
                    score_team_1: s1,
                    score_team_2: s2,
                    match_status: 'completed'
                }
            }
        );
        console.log(`[apiScores] ${match.match_id} → HTTP ${status}`);
    }
}

// ─── Match score helpers ──────────────────────────────────────────────────────

/**
 * Finds the first upcoming Round 1 match card on /player and opens its detail page.
 */
export async function openFirstRound1Match(page: Page): Promise<string> {
    const round1Card = page.locator('.matches-grid').first()
        .locator('.match-card')
        .filter({ has: page.locator('.round-badge', { hasText: /Round 1/i }) })
        .first();
    await round1Card.waitFor({ timeout: 15_000 });
    await round1Card.click();
    await page.waitForURL('**/player/match/**', { timeout: 15_000 });
    const url = page.url();
    return url.split('/').pop() ?? '';
}

/**
 * On the match-detail page: enters score and saves.
 * Assumes we are already on /player/match/:id
 */
export async function submitScore(page: Page, myScore: number, opponentScore: number) {
    const editBtn = page.locator('button:has-text("Edit Score")');
    if (await editBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await editBtn.click();
    } else {
        await page.locator('button:has-text("Enter Score")').click();
    }

    const scoreInputs = page.locator('.score-input-small');
    await scoreInputs.nth(0).fill(String(myScore));
    await scoreInputs.nth(1).fill(String(opponentScore));

    await page.locator('button:has-text("Save Score")').click();
    await page.waitForSelector('.completed-msg', { timeout: 15_000 });
}

/**
 * Full flow: login as player → select league → open first Round 1 match → submit score → go back → logout
 */
export async function loginAndSubmitScore(
    page: Page,
    email: string,
    password: string,
    leagueName: string,
    myScore: number,
    opponentScore: number
) {
    await playerLogin(page, email, password);
    await selectLeague(page, leagueName);
    await openFirstRound1Match(page);
    await submitScore(page, myScore, opponentScore);
    await page.locator('button:has-text("Back to Dashboard")').first().click();
    await page.waitForURL('**/player', { timeout: 10_000 });
    await logout(page);
}

// ─── Reusable Flow Helpers ────────────────────────────────────────────────────

export const ALL_PLAYERS = [
    'dhirender.b@test.com',
    'usha.b@test.com',
    'aditya.butola@test.com',
    'shreya.butola@test.com',
    'animesh.butola@test.com',
    'santoshi.butola@test.com',
    'samar.butola@test.com',
    'deepak.panwar@test.com',
    'pratibha.panwar@test.com',
];

/**
 * Slots a round, fills default time/court, and saves.
 * Returns an array of groups, each containing an array of player emails.
 */
export async function adminSlotAndSaveRound(page: Page, roundText: string): Promise<string[][]> {
    // Intercept the save-round network request so we know if it fires
    const savePromise = page.waitForRequest(req => req.url().includes('/api/v1/league/round') && req.method() === 'POST', { timeout: 15_000 }).catch(() => null);

    await page.locator(`button:has-text("${roundText}")`).click();
    await page.waitForSelector('.match-box', { timeout: 20_000 });

    const groupHeaders = page.locator('.card .flex-center[style*="cursor: pointer"]');
    const groupCount = await groupHeaders.count();

    for (let g = 0; g < groupCount; g++) {
        const header = groupHeaders.nth(g);
        const arrow = header.locator('span[style*="rotate"]').first();
        const transform = await arrow.getAttribute('style');
        if (transform?.includes('rotate(0deg)')) {
            await header.click();
            await page.waitForTimeout(400);
        }
    }

    await page.waitForSelector('.match-box', { timeout: 10_000 });

    const groupPlayerEmails: string[][] = [];
    const groupCards = page.locator('.card').filter({ has: page.locator('.match-box') });
    const numGroups = await groupCards.count();

    for (let g = 0; g < numGroups; g++) {
        const card = groupCards.nth(g);
        const playerNames = await card.locator('div[style*="font-weight: 500"]').allTextContents();
        const uniqueNames = [...new Set(playerNames.map(n => n.trim()).filter(Boolean))];

        const emails = uniqueNames
            .map(name => ALL_PLAYERS.find(e => e.startsWith(name.toLowerCase().split(' ')[0])))
            .filter((e): e is string => !!e);

        groupPlayerEmails.push([...new Set(emails)]);
    }

    // Verify the save request was actually sent to the backend
    const saveReq = await savePromise;
    if (saveReq) {
        const resp = await saveReq.response();
        console.log(`[adminSlotAndSaveRound] Save POST ${resp?.status()} — round saved to DB`);
    } else {
        console.warn('[adminSlotAndSaveRound] WARNING: /api/v1/league/round was never called — saveRoundById skipped (league() undefined?)');
    }

    // slotNextRound() auto-saves; wait for the network call to finish
    await page.waitForLoadState('networkidle', { timeout: 15_000 });

    console.log(`[adminSlotAndSaveRound] Groups found: ${groupPlayerEmails.map((g, i) => `Group${i}=[${g.join(',')}]`).join(', ')}`);
    return groupPlayerEmails;
}

/**
 * Submits scores for all remaining matches of a specific round for a list of players.
 * Uses a full page reload after each submission so the match count is always read from
 * the actual DB state rather than from the Angular local signal, which can be stale.
 */
export async function submitRemainingGroupScores(
    page: Page,
    playerEmails: string[],
    startIndex: number,
    leagueName: string,
    password: string,
    roundPattern: RegExp
) {
    let scoreIdx = 6;
    for (let i = startIndex; i < playerEmails.length; i++) {
        const email = playerEmails[i];
        await playerLogin(page, email, password);
        await selectLeague(page, leagueName);

        while (true) {
            const roundCards = page.locator('.matches-grid').first()
                .locator('.match-card')
                .filter({ has: page.locator('.round-badge', { hasText: roundPattern }) });

            const remaining = await roundCards.count();
            console.log(`[submitScores] ${email}: ${remaining} match cards for ${roundPattern}`);
            if (remaining === 0) break;

            await roundCards.first().click();
            await page.waitForURL('**/player/match/**', { timeout: 15_000 });
            await page.waitForLoadState('networkidle');

            const myScore = 11;
            const oppScore = scoreIdx % 2 === 0 ? 5 : 7;
            scoreIdx++;

            const completedMsg = page.locator('.completed-msg');
            const editBtn = page.locator('button:has-text("Edit Score")');
            const enterBtn = page.locator('button:has-text("Enter Score")');

            if (await completedMsg.isVisible({ timeout: 1000 }).catch(() => false)) {
                // Match already completed — navigate back without submitting
            } else if (await editBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
                await editBtn.click();
                const scoreInputs = page.locator('.score-input-small');
                await scoreInputs.nth(0).fill(String(myScore));
                await scoreInputs.nth(1).fill(String(oppScore));
                await page.locator('button:has-text("Save Score")').click();
                // Wait for all network requests to finish before navigating away.
                // page.goto (used inside selectLeague) aborts in-flight requests, so the
                // score POST must complete first or it gets cancelled and nothing is saved.
                await page.waitForLoadState('networkidle', { timeout: 30_000 });
            } else if (await enterBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
                await enterBtn.click();
                const scoreInputs = page.locator('.score-input-small');
                await scoreInputs.nth(0).fill(String(myScore));
                await scoreInputs.nth(1).fill(String(oppScore));
                await page.locator('button:has-text("Save Score")').click();
                await page.waitForLoadState('networkidle', { timeout: 30_000 });
            }
            // else: score button not visible — navigate back without submitting

            // Full page reload so the next iteration reads real DB state, not Angular signal cache.
            await selectLeague(page, leagueName);
        }

        await logout(page);
    }
}
