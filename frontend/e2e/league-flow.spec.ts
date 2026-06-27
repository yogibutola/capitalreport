import { test, expect } from '@playwright/test';
import {
    runSeeder,
    adminLogin,
    adminSlotAndSaveRound,
    submitAllMatchScoresViaApi
} from './helpers';

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';

test('League flow: 9 players → slot R1 → complete R1 & R2', async ({ page }) => {

    // STEP 1: Seed test data (9 players, group_size=4)
    console.log('\n━━━ STEP 1: Seeding test data ━━━');
    const leagueName = runSeeder();
    console.log('League name:', leagueName);

    // STEP 2: Admin navigates to the slotting page and slots Round 1
    console.log('\n━━━ STEP 2: Admin slots Round 1 ━━━');
    await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.waitForSelector('text=' + leagueName, { timeout: 15_000 });
    await page.locator('.admin-league-item').filter({ hasText: leagueName }).click();
    await page.waitForURL('**/admin/league/**', { timeout: 15_000 });
    await page.locator('a:has-text("View and Slot")').click();
    await page.waitForURL('**/league/slotting**', { timeout: 15_000 });

    const groups = await adminSlotAndSaveRound(page, 'Slot Round 1');

    // 9 players with group_size=4 → 2 groups: G1=5, G2=4
    expect(groups).toHaveLength(2);
    expect(groups[0]).toHaveLength(5);
    expect(groups[1]).toHaveLength(4);
    console.log(`Groups: G1=${groups[0].length} players, G2=${groups[1].length} players ✓`);

    // Verify Round 1 match count via API: 5-player group → 5 matches, 4-player group → 3 matches
    const token = await page.evaluate(() => {
        const u = JSON.parse(localStorage.getItem('pickleball_user') || '{}');
        return (u as any).token || '';
    });

    const r1Matches = await page.evaluate(async ({ name, tok }: { name: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/name/${encodeURIComponent(name)}`, {
            headers: { Authorization: `Bearer ${tok}` }
        });
        const d = await res.json();
        return (d.matches as any[] || []).filter((m: any) => Number(m.round_id) === 1);
    }, { name: leagueName, tok: token });

    expect(r1Matches).toHaveLength(8); // 5 (G1) + 3 (G2)
    console.log(`Round 1 matches created: ${r1Matches.length} ✓`);

    // STEP 3: Submit all Round 1 scores via API.
    // The last submission synchronously triggers auto-slotting of Round 2 on the backend.
    console.log('\n━━━ STEP 3: Submit Round 1 scores via API ━━━');
    await submitAllMatchScoresViaApi(page, leagueName, 1);

    // Verify Round 2 was auto-slotted after Round 1 completed
    const r2Matches = await page.evaluate(async ({ name, tok }: { name: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/name/${encodeURIComponent(name)}`, {
            headers: { Authorization: `Bearer ${tok}` }
        });
        const d = await res.json();
        return (d.matches as any[] || []).filter((m: any) => Number(m.round_id) === 2);
    }, { name: leagueName, tok: token });

    expect(r2Matches).toHaveLength(8);
    expect(r2Matches.every((m: any) => m.match_status !== 'completed')).toBe(true);
    console.log(`Round 2 auto-slotted: ${r2Matches.length} matches, all pending ✓`);

    // STEP 4: Submit all Round 2 scores via API.
    // Completing Round 2 creates the Round 3 group structure (Day 2 setup).
    console.log('\n━━━ STEP 4: Submit Round 2 scores via API ━━━');
    await submitAllMatchScoresViaApi(page, leagueName, 2);

    // Verify all Round 2 matches are now completed
    const r2Final = await page.evaluate(async ({ name, tok }: { name: string; tok: string }) => {
        const res = await fetch(`/api/v1/league/name/${encodeURIComponent(name)}`, {
            headers: { Authorization: `Bearer ${tok}` }
        });
        const d = await res.json();
        return (d.matches as any[] || []).filter((m: any) => Number(m.round_id) === 2);
    }, { name: leagueName, tok: token });

    expect(r2Final).toHaveLength(8);
    expect(r2Final.every((m: any) => m.match_status === 'completed')).toBe(true);
    console.log(`Round 2 completed: ${r2Final.filter((m: any) => m.match_status === 'completed').length}/8 ✓`);

    console.log('\n✅ League flow test passed!');
});
