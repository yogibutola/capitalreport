import { test, expect } from '@playwright/test';
import { runSeeder, adminLogin, playerLogin, logout, ALL_PLAYERS } from './helpers';

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';
const PLAYER_PASSWORD = 'Password@123';

/**
 * Club "Active Season" tab — sits after "Leagues" / "Tournaments" in the club header
 * nav and lists the club's active leagues/tournaments with round progress.
 * Requires the backend + Mongo; seeds an active league via test_data_seeder.py.
 */
test.describe('Active Season tab (club)', () => {
    let leagueName: string;

    test.beforeAll(() => {
        leagueName = runSeeder();
    });

    test('tab sits after Leagues / Tournaments and only one tab is highlighted at a time', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);

        const tabs = page.locator('.header-nav-tabs .nav-tab-link');
        const leagues = tabs.filter({ hasText: 'Leagues' });
        const season = tabs.filter({ hasText: 'Active Season' });
        await expect(tabs.filter({ hasText: 'Manage' })).toHaveCount(0);
        await expect(tabs.nth(0)).toHaveText('Leagues');
        await expect(tabs.nth(1)).toHaveText('Tournaments');
        await expect(tabs.nth(2)).toHaveText('Active Season');
        await expect(tabs.nth(3)).toHaveText('Club Profile');
        await expect(season).toHaveAttribute('href', '/admin/season');

        // After login (on /admin/leagues) only Leagues is active
        await expect(leagues).toHaveClass(/\bactive\b/);
        await expect(season).not.toHaveClass(/\bactive\b/);

        await season.click();
        await page.waitForURL('**/admin/season', { timeout: 15_000 });
        await expect(season).toHaveClass(/\bactive\b/);
        await expect(leagues).not.toHaveClass(/\bactive\b/);

        // League detail pages highlight the Leagues tab, never the season tab
        await page.goto('/admin/leagues');
        await page.locator('.admin-league-item').filter({ hasText: leagueName }).click();
        await page.waitForURL('**/admin/league/**', { timeout: 15_000 });
        await expect(leagues).toHaveClass(/\bactive\b/);
        await expect(season).not.toHaveClass(/\bactive\b/);
    });

    test('lists the seeded active league with its player count and progress', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);

        const progressResp = page.waitForResponse(
            resp => resp.url().includes(`/api/v1/league/name/${encodeURIComponent(leagueName)}`) &&
                resp.request().method() === 'GET',
            { timeout: 20_000 }
        );
        await page.goto('/admin/season');
        await progressResp;

        await expect(page.getByRole('heading', { level: 1 })).toHaveText('Active Season');
        await expect(page.getByTestId('season-empty')).toHaveCount(0);

        const card = page.getByTestId('season-league').filter({ hasText: leagueName });
        await expect(card).toBeVisible();
        await expect(card.locator('.season-badge')).toHaveText(/active/i);
        await expect(card).toContainText(`${ALL_PLAYERS.length} players`);
        // Freshly seeded league has no rounds slotted yet
        await expect(card).toContainText('Not slotted yet');
        await expect(card.locator('.season-progress')).toHaveCount(0);

        // Banner counts reflect the loaded league
        const leaguesStat = Number(await page.getByTestId('season-stat-leagues').locator('.season-stat-number').innerText());
        expect(leaguesStat).toBeGreaterThanOrEqual(1);
        const playersStat = Number(await page.getByTestId('season-stat-players').locator('.season-stat-number').innerText());
        expect(playersStat).toBeGreaterThanOrEqual(ALL_PLAYERS.length);

        // Actions link into the existing league pages
        await expect(card.getByRole('link', { name: 'Slot rounds' })).toHaveAttribute(
            'href',
            `/league/slotting?league_id=${encodeURIComponent(leagueName)}`
        );
        await card.getByRole('link', { name: 'Open league' }).click();
        await page.waitForURL('**/admin/league/**', { timeout: 15_000 });
        await expect(page.locator('body')).toContainText(leagueName);
    });

    test('players never see the Active Season tab and cannot open the route', async ({ page }) => {
        await playerLogin(page, ALL_PLAYERS[0], PLAYER_PASSWORD);
        const tabs = page.locator('.header-nav-tabs .nav-tab-link');
        await expect(tabs.filter({ hasText: 'Active Season' })).toHaveCount(0);
        await expect(tabs.filter({ hasText: 'Manage' })).toHaveCount(0);

        await page.goto('/admin/season');
        await page.waitForLoadState('networkidle');
        expect(page.url()).not.toMatch(/\/admin\/season$/);
        await logout(page);
    });
});
