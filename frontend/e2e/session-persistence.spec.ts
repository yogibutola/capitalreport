import { test, expect } from '@playwright/test';
import { runSeeder, adminLogin, playerLogin, ALL_PLAYERS } from './helpers';

/**
 * Regression coverage for a bug where the session lives only in localStorage
 * (browser-only), but every route is SSR-rendered. A hard refresh used to hit
 * the server with no session available, and the admin/player auth checks
 * would redirect to a login screen before the client ever got a chance to
 * restore the real session from localStorage. See admin.guard.ts /
 * dashboard.ts (`/league`) for the fix.
 */

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';
const PLAYER_PASSWORD = 'Password@123';

test('Refreshing /admin/leagues keeps an admin session instead of bouncing to login', async ({ page }) => {
    runSeeder();

    await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    expect(page.url()).toContain('/admin/leagues');

    await page.reload();
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('/admin/leagues');
    expect(page.url()).not.toContain('/admin/login');
});

test('Visiting bare /admin redirects a signed-in club to the Leagues tab', async ({ page }) => {
    runSeeder();

    await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await page.goto('/admin');
    await page.waitForURL('**/admin/leagues', { timeout: 15_000 });
    expect(page.url()).not.toContain('/admin/login');
});

test('Refreshing /league keeps a player session instead of bouncing to login', async ({ page }) => {
    runSeeder();

    await playerLogin(page, ALL_PLAYERS[0], PLAYER_PASSWORD);
    expect(page.url()).toContain('/league');

    await page.reload();
    await page.waitForLoadState('networkidle');

    expect(page.url()).toContain('/league');
    expect(page.url()).not.toContain('/login');
});
