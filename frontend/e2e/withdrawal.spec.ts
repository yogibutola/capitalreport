import { test, expect } from '@playwright/test';
import {
    runSeeder,
    adminLogin,
    playerLogin,
    logout,
    selectLeague,
    adminSlotAndSaveRound,
    submitAllMatchScoresViaApi
} from './helpers';

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';
const PLAYER_PASSWORD = 'Password@123';

const WITHDRAWING_PLAYER = 'pratibha.panwar@test.com';
const WITHDRAWING_PLAYER_NAME = 'Pratibha Panwar';

test('Player Withdrawal E2E: seed → player withdraws → admin verifies exclusion', async ({ page }) => {

    // STEP 1: Seed test data
    console.log('\n━━━ STEP 1: Seeding test data ━━━');
    const leagueName = runSeeder();
    console.log('League name:', leagueName);

    // STEP 2: Admin slots Round 1
    console.log('\n━━━ STEP 2: Admin slots Round 1 ━━━');
    await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.waitForSelector('text=' + leagueName, { timeout: 15_000 });
    await page.locator('.admin-league-item').filter({ hasText: leagueName }).click();
    await page.waitForURL('**/admin/league/**', { timeout: 15_000 });
    await page.locator('a:has-text("View and Slot")').click();
    await page.waitForURL('**/league/slotting**', { timeout: 15_000 });
    await adminSlotAndSaveRound(page, 'Slot Round 1');

    // STEP 3: Submit all Round 1 scores via API (setup step — not under test).
    // Submitting the last match triggers server-side auto-slotting of Round 2 synchronously.
    console.log('\n━━━ STEP 3: Submit Round 1 scores via API ━━━');
    await submitAllMatchScoresViaApi(page, leagueName, 1);

    // STEP 4: Submit all Round 2 scores via API.
    // Completing Round 2 triggers server-side creation of Round 3 group structure.
    console.log('\n━━━ STEP 4: Submit Round 2 scores via API ━━━');
    await submitAllMatchScoresViaApi(page, leagueName, 2);

    await logout(page);

    // STEP 5: Player logs in and withdraws from Day 2
    console.log(`\n━━━ STEP 5: Player ${WITHDRAWING_PLAYER} withdraws from Day 2 ━━━`);
    await playerLogin(page, WITHDRAWING_PLAYER, PLAYER_PASSWORD);
    await selectLeague(page, leagueName);

    page.on('dialog', async dialog => {
        expect(dialog.message()).toContain('Please enter a reason');
        await dialog.accept('Test withdrawal reason');
    });

    await page.locator('.nav-item').filter({ hasText: 'Withdraw' }).click();
    await expect(page.locator('h3.section-title:has-text("Play Days")')).toBeVisible({ timeout: 10_000 });

    const day2Row = page.locator('table tbody tr').nth(1);
    await expect(day2Row).toContainText('Day 2');
    await day2Row.locator('button:has-text("Withdraw")').click();

    await expect(day2Row.locator('span:has-text("Withdrawn")')).toBeVisible({ timeout: 10_000 });
    await expect(day2Row).toContainText('Reason: Test withdrawal reason');

    console.log('Withdrawal successful.');
    await logout(page);

    // STEP 6: Admin verifies withdrawn player is excluded from Day 2 slotting
    console.log('\n━━━ STEP 6: Admin verifies exclusion ━━━');
    await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    const token = await page.evaluate(() => {
        const user = JSON.parse(localStorage.getItem('pickleball_user') || '{}');
        return (user as any).token || '';
    });

    const leagueId = await page.evaluate(async ({ name, tok }: { name: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/name/${name}`, {
            headers: { Authorization: `Bearer ${tok}` }
        });
        const data = await res.json();
        return data.league_id as string;
    }, { name: leagueName, tok: token });

    console.log('Resolved leagueId:', leagueId);
    expect(leagueId).toBeTruthy();

    const slotResponse = await page.evaluate(async ({ id, tok }: { id: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/${id}/day/2/slot`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' }
        });
        return { status: res.status, body: await res.text() };
    }, { id: leagueId, tok: token });

    console.log('Day 2 slot API response:', slotResponse.status, slotResponse.body);
    expect(slotResponse.status).toBe(200);

    // Verify via the API that Round 3 (Day 2, first round) match documents do NOT include
    // the withdrawn player. We check the match-player emails directly rather than reading
    // the slotting UI, which shows all historical rounds and would show the player from
    // Round 1/2 even if correctly excluded from Round 3.
    const round3Emails = await page.evaluate(async ({ name, tok }: { name: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/name/${encodeURIComponent(name)}`, {
            headers: { Authorization: `Bearer ${tok}` }
        });
        const d = await res.json();
        const emails = new Set<string>();
        (d.matches as any[] || [])
            .filter((m: any) => Number(m.round_id) === 3)
            .forEach((m: any) => {
                [m.team_one?.player_one, m.team_one?.player_two,
                 m.team_two?.player_one, m.team_two?.player_two].forEach((p: any) => {
                    if (p?.email) emails.add((p.email as string).toLowerCase());
                });
            });
        return [...emails];
    }, { name: leagueName, tok: token });

    console.log('Round 3 player emails:', round3Emails);
    expect(round3Emails.length).toBeGreaterThan(0); // sanity: Round 3 was actually created
    expect(round3Emails).not.toContain(WITHDRAWING_PLAYER.toLowerCase());

    console.log(`\n✅ Withdrawal E2E test passed! ${WITHDRAWING_PLAYER_NAME} correctly excluded from Day 2.`);
});
