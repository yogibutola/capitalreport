import { test, expect } from '@playwright/test';
import { runSeeder, adminLogin, playerLogin, logout, ALL_PLAYERS } from './helpers';

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';
const PLAYER_PASSWORD = 'Password@123';

/**
 * Club nav: "Active Season" is the first tab, then "Leagues" / "Tournaments". The
 * post-login landing page is /admin/season. There is no "Manage" hub tab any
 * more — /admin redirects to /admin/season.
 * Requires the backend + Mongo; seeds a league via test_data_seeder.py.
 */
test.describe('Leagues / Tournaments tabs (club)', () => {
    let leagueName: string;

    test.beforeAll(() => {
        leagueName = runSeeder();
    });

    test('Active Season leads the tabs and is the landing page, Leagues and Tournaments route to their own pages', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);

        const tabs = page.locator('.header-nav-tabs .nav-tab-link');
        const leagues = tabs.filter({ hasText: 'Leagues' });
        const tournaments = tabs.filter({ hasText: 'Tournaments' });

        // No Manage tab anywhere in the club nav
        await expect(tabs.filter({ hasText: 'Manage' })).toHaveCount(0);
        await expect(tabs).toHaveCount(4);
        await expect(tabs.nth(0)).toHaveText('Active Season');
        await expect(tabs.nth(1)).toHaveText('Leagues');
        await expect(tabs.nth(2)).toHaveText('Tournaments');
        await expect(tabs.nth(3)).toHaveText('Club Profile');
        await expect(leagues).toHaveAttribute('href', '/admin/leagues');
        await expect(tournaments).toHaveAttribute('href', '/admin/tournaments');

        // The club's name sits at the far right of the tab row, after the last tab
        const clubName = page.getByTestId('header-club-name');
        await expect(clubName).toBeVisible();
        await expect(clubName).not.toBeEmpty();
        // Rendered as a brand-lime badge so it stands out from the muted tabs
        const [badgeBg, ballColour] = await clubName.evaluate((el) => {
            const probe = document.createElement('span');
            probe.style.backgroundColor = 'var(--ball)';
            document.body.appendChild(probe);
            const ball = getComputedStyle(probe).backgroundColor;
            probe.remove();
            return [getComputedStyle(el).backgroundColor, ball];
        });
        expect(badgeBg).toBe(ballColour);
        const lastTabBox = (await tabs.nth(3).boundingBox())!;
        const clubBox = (await clubName.boundingBox())!;
        const rowBox = (await page.locator('.header-nav-row').boundingBox())!;
        expect(clubBox.x).toBeGreaterThan(lastTabBox.x + lastTabBox.width);
        expect(rowBox.x + rowBox.width - (clubBox.x + clubBox.width)).toBeLessThanOrEqual(30);

        // Login lands on the Active Season page with only its tab active
        await expect(page).toHaveURL(/\/admin\/season$/);
        await expect(page.getByRole('heading', { level: 1 })).toHaveText('Active Season');
        await expect(tabs.nth(0)).toHaveClass(/\bactive\b/);
        await expect(leagues).not.toHaveClass(/\bactive\b/);

        // Leagues page has its own header, create button, and active tab
        await leagues.click();
        await page.waitForURL('**/admin/leagues', { timeout: 15_000 });
        await expect(page.getByTestId('admin-leagues-page')).toBeVisible();
        await expect(page.getByRole('heading', { level: 1 })).toHaveText('Leagues');
        await expect(page.locator('.admin-league-item').filter({ hasText: leagueName })).toBeVisible();
        await expect(page.getByRole('button', { name: '+ New League' })).toBeVisible();
        await expect(page.getByRole('button', { name: '+ New Tournament' })).toHaveCount(0);
        await expect(leagues).toHaveClass(/\bactive\b/);
        await expect(tournaments).not.toHaveClass(/\bactive\b/);

        const total = Number(await page.getByTestId('leagues-stat-total').locator('.admin-stat-number').innerText());
        expect(total).toBeGreaterThanOrEqual(1);

        // Tournaments page has its own header, create button, and active tab
        await tournaments.click();
        await page.waitForURL('**/admin/tournaments', { timeout: 15_000 });
        await expect(page.getByTestId('admin-tournaments-page')).toBeVisible();
        await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tournaments');
        await expect(page.getByRole('button', { name: '+ New Tournament' })).toBeVisible();
        await expect(page.getByRole('button', { name: '+ New League' })).toHaveCount(0);
        await expect(tournaments).toHaveClass(/\bactive\b/);
        await expect(leagues).not.toHaveClass(/\bactive\b/);
    });

    test('bare /admin redirects to the Active Season tab', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/leagues');
        await page.goto('/admin');
        await page.waitForURL('**/admin/season', { timeout: 15_000 });
        await expect(page.getByRole('heading', { level: 1 })).toHaveText('Active Season');
        await expect(page.locator('.header-nav-tabs .nav-tab-link').filter({ hasText: 'Active Season' }))
            .toHaveClass(/\bactive\b/);
    });

    test('create and detail pages keep the matching tab highlighted and go back to it', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        const tabs = page.locator('.header-nav-tabs .nav-tab-link');

        // Create League → Leagues tab active, Back returns to /admin/leagues
        await page.goto('/admin/create-league');
        await expect(tabs.filter({ hasText: 'Leagues' })).toHaveClass(/\bactive\b/);
        await page.getByRole('link', { name: 'Back' }).click();
        await page.waitForURL('**/admin/leagues', { timeout: 15_000 });

        // League detail → Leagues tab active, Back to Leagues returns to /admin/leagues
        await page.locator('.admin-league-item').filter({ hasText: leagueName }).click();
        await page.waitForURL('**/admin/league/**', { timeout: 15_000 });
        await expect(tabs.filter({ hasText: 'Leagues' })).toHaveClass(/\bactive\b/);
        await page.getByRole('link', { name: 'Back to Leagues' }).click();
        await page.waitForURL('**/admin/leagues', { timeout: 15_000 });

        // Create Tournament → Tournaments tab active, Back returns to /admin/tournaments
        await page.goto('/admin/create-tournament');
        await expect(tabs.filter({ hasText: 'Tournaments' })).toHaveClass(/\bactive\b/);
        await expect(tabs.filter({ hasText: 'Leagues' })).not.toHaveClass(/\bactive\b/);
        await page.getByRole('link', { name: 'Back' }).click();
        await page.waitForURL('**/admin/tournaments', { timeout: 15_000 });
    });

    test('players never see the club tabs and cannot open the routes', async ({ page }) => {
        await playerLogin(page, ALL_PLAYERS[0], PLAYER_PASSWORD);
        const tabs = page.locator('.header-nav-tabs .nav-tab-link');
        await expect(tabs.filter({ hasText: 'Manage' })).toHaveCount(0);
        await expect(page.getByTestId('header-club-name')).toHaveCount(0);
        // Players have their own Leagues/Tournaments tabs pointing at /player/...
        await expect(tabs.filter({ hasText: 'Leagues' })).toHaveAttribute('href', '/player/leagues');
        await expect(tabs.filter({ hasText: 'Tournaments' })).toHaveAttribute('href', '/player/tournaments');

        for (const url of ['/admin', '/admin/season', '/admin/leagues', '/admin/tournaments']) {
            await page.goto(url);
            await page.waitForLoadState('networkidle');
            expect(page.url()).not.toMatch(/\/admin(\/season|\/leagues|\/tournaments)?$/);
        }
        await logout(page);
    });
});
