import { test, expect } from '@playwright/test';
import { adminLogin, logout } from './helpers';

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';

/**
 * The optional DUPR band on the create-league form.
 *
 * Both bounds are optional — a league that sets neither accepts any rating, which
 * is what every league created before this field existed does. Requires the
 * backend + Mongo and the test_pro club account (see e2e-seeded-specs setup).
 */
test.describe('Create league: DUPR range', () => {
    test('both bounds are optional and default to blank', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-league');
        await page.waitForLoadState('networkidle');

        await expect(page.locator('#field-duprMin')).toHaveValue('');
        await expect(page.locator('#field-duprMax')).toHaveValue('');
        await expect(page.getByText('Leave both blank to allow any rating')).toBeVisible();

        await logout(page);
    });

    test('an inverted range blocks submit', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-league');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-name', `Inverted DUPR ${Date.now()}`);
        await page.fill('#field-startDate', '2026-11-01');
        await page.fill('#field-duprMin', '4.5');
        await page.fill('#field-duprMax', '3.0');
        await page.click('button[type="submit"]');

        await expect(page.getByText('Max rating must be at least the min rating.')).toBeVisible();
        // Client-side rejection — we never left the form.
        await expect(page).toHaveURL(/\/admin\/create-league$/);

        // Correcting the range clears the message and lets the league through.
        await page.fill('#field-duprMax', '5.0');
        await expect(
            page.getByText('Max rating must be at least the min rating.')
        ).toBeHidden();

        await logout(page);
    });

    test('a banded league is created and the band reaches the player listing', async ({ page }) => {
        const name = `DUPR Band ${Date.now()}`;

        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-league');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-name', name);
        await page.fill('#field-startDate', '2026-11-01');
        await page.fill('#field-duprMin', '3');
        await page.fill('#field-duprMax', '4');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/admin/leagues', { timeout: 20_000 });
        await expect(page.getByText(name)).toBeVisible();

        await logout(page);
    });

    test('a league with no band is created with both bounds left blank', async ({ page }) => {
        const name = `Any Rating ${Date.now()}`;

        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-league');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-name', name);
        await page.fill('#field-startDate', '2026-11-01');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/admin/leagues', { timeout: 20_000 });
        await expect(page.getByText(name)).toBeVisible();

        await logout(page);
    });
});
