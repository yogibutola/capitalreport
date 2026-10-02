import { test, expect } from '@playwright/test';
import { runPlatformSeeder, platformLogin, SUPERADMIN } from './helpers';
import { PHONE, expectNoHorizontalOverflow } from './mobile-helpers';

/**
 * Hidden application-admin console at /x9k2-console.
 *
 * REQUIRES the FastAPI backend to be running with:
 *     SUPERADMIN_EMAILS=platform.admin@test.com
 * so the seeded account is elevated to the superadmin role on sign-in.
 */
test.describe('Platform console', () => {
    test.beforeAll(() => {
        runPlatformSeeder();
    });

    test('lists clubs & players, adds and removes each, and records the activity', async ({ page }) => {
        await platformLogin(page, SUPERADMIN.email, SUPERADMIN.password);

        // ── Clubs tab lists the seeded club ─────────────────────────────────
        await expect(page.locator('.pc-tabs button', { hasText: 'Clubs' })).toBeVisible();
        await expect(page.locator('.pc-table', { hasText: 'pc.club@test.com' })).toBeVisible();

        // ── Add a club ─────────────────────────────────────────────────────
        const newClubEmail = `pc.new.${Date.now()}@test.com`;
        await page.click('button:has-text("+ Add club")');
        // A club is run by a person: the form creates the organiser's account too.
        await page.fill('input[name="firstName"]', 'Nova');
        await page.fill('input[name="lastName"]', 'Organiser');
        await page.fill('input[name="clubName"]', 'Brand New Club');
        await page.fill('input[name="email"]', newClubEmail);
        await page.fill('input[name="password"]', 'Password@123');
        await page.click('button:has-text("Create club")');
        await expect(page.locator('.pc-table', { hasText: newClubEmail })).toBeVisible({ timeout: 10_000 });

        // ── Remove it (confirm dialog) ─────────────────────────────────────
        const clubRow = page.locator('tr', { hasText: newClubEmail });
        await clubRow.locator('button:has-text("Remove")').click();
        await page.locator('app-confirm-host button:has-text("Remove Club")').click();
        await expect(page.locator('.pc-table', { hasText: newClubEmail })).toHaveCount(0, { timeout: 10_000 });

        // The organiser keeps their account: removing a club isn't removing a person.
        await page.click('.pc-tabs button:has-text("Players")');
        await expect(page.locator('.pc-table', { hasText: newClubEmail })).toBeVisible({ timeout: 10_000 });
        await page.click('.pc-tabs button:has-text("Clubs")');

        // ── Players tab ───────────────────────────────────────────────────
        await page.click('.pc-tabs button:has-text("Players")');
        await expect(page.locator('.pc-table', { hasText: 'pc.player1@test.com' })).toBeVisible();

        const newPlayerEmail = `pc.newp.${Date.now()}@test.com`;
        await page.click('button:has-text("+ Add player")');
        await page.fill('input[name="firstName"]', 'Fresh');
        await page.fill('input[name="lastName"]', 'Player');
        await page.fill('input[name="email"]', newPlayerEmail);
        await page.fill('input[name="password"]', 'Password@123');
        await page.click('button:has-text("Create player")');
        await expect(page.locator('.pc-table', { hasText: newPlayerEmail })).toBeVisible({ timeout: 10_000 });

        const playerRow = page.locator('tr', { hasText: newPlayerEmail });
        await playerRow.locator('button:has-text("Remove")').click();
        await page.locator('app-confirm-host button:has-text("Remove Player")').click();
        await expect(page.locator('.pc-table', { hasText: newPlayerEmail })).toHaveCount(0, { timeout: 10_000 });

        // ── Activity tab shows the superadmin's own actions ────────────────
        await page.click('.pc-tabs button:has-text("Activity")');
        await page.fill('input[placeholder="Filter by user email"]', SUPERADMIN.email);
        await page.click('button:has-text("Filter")');
        await expect(
            page.locator('.pc-table tr', { hasText: SUPERADMIN.email }).first()
        ).toBeVisible({ timeout: 10_000 });
    });

    test('refreshing /x9k2-console keeps the superadmin session instead of bouncing to login', async ({ page }) => {
        await platformLogin(page, SUPERADMIN.email, SUPERADMIN.password);

        await page.reload();
        await page.waitForLoadState('networkidle');

        expect(page.url()).toContain('/x9k2-console');
        expect(page.url()).not.toContain('/x9k2-console/login');
        await expect(page.locator('h2', { hasText: 'Platform Console' })).toBeVisible();
    });

    // The console had no responsive rules at all: its filter row alone (a 220px
    // minimum input plus two buttons) was wider than a phone.
    test('fits a 390px phone, with its tables scrolling instead of the page', async ({ page }) => {
        await page.setViewportSize(PHONE);
        await platformLogin(page, SUPERADMIN.email, SUPERADMIN.password);
        await page.waitForLoadState('networkidle');

        await expectNoHorizontalOverflow(page, 'platform console (clubs)');

        await page.click('.pc-tabs button:has-text("Activity")');
        await page.waitForLoadState('networkidle');
        await expectNoHorizontalOverflow(page, 'platform console (activity)');

        // The filter input must drop onto its own line rather than shove the
        // Filter/Clear buttons off screen.
        const input = (await page.locator('input[placeholder="Filter by user email"]').boundingBox())!;
        const filterBtn = (await page.locator('button:has-text("Filter")').first().boundingBox())!;
        expect(filterBtn.y, 'the filter controls are still crammed onto one row').toBeGreaterThan(
            input.y + input.height - 2
        );
    });

    test('the console URL is not reachable without the superadmin role', async ({ page }) => {
        // Fresh context - no session. The guard must bounce us to the hidden login.
        await page.goto('/x9k2-console');
        await page.waitForURL('**/x9k2-console/login', { timeout: 10_000 });
        await expect(page.locator('h2', { hasText: 'Platform Console' })).toBeVisible();
    });
});
