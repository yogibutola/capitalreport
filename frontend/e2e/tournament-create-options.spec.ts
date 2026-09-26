import { test, expect } from '@playwright/test';
import { adminLogin, logout } from './helpers';

const ADMIN_EMAIL = 'test_pro@gmail.com';
const ADMIN_PASSWORD = 'Password@123';

/**
 * Age group + Mixed Doubles on the create-tournament form.
 *
 * Both are labels: they are stored and rendered on the listing / detail pages
 * but never gate registration. Requires the backend + Mongo and the test_pro
 * club account (see e2e-seeded-specs setup).
 */
test.describe('Create tournament: age group + match format', () => {
    test('the form offers three match formats and the age-group presets', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-tournament');
        await page.waitForLoadState('networkidle');

        const format = page.locator('#field-format');
        await expect(format.locator('option')).toHaveCount(3);
        await expect(format.locator('option')).toHaveText(['Doubles', 'Singles', 'Mixed Doubles']);

        const ageGroup = page.locator('#field-ageGroup');
        await expect(ageGroup.locator('option')).toHaveText([
            'Open (all ages)',
            '19+',
            '35+',
            '50+',
            '60+',
            '70+',
            'Custom…',
        ]);
        // Open is the default, and it keeps the custom range hidden.
        await expect(ageGroup).toHaveValue('open');
        await expect(page.getByTestId('custom-age-range')).toBeHidden();

        await logout(page);
    });

    test('Custom reveals the age range, and an empty range blocks submit', async ({ page }) => {
        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-tournament');
        await page.waitForLoadState('networkidle');

        const range = page.getByTestId('custom-age-range');
        await page.locator('#field-ageGroup').selectOption('custom');
        await expect(range).toBeVisible();

        // A custom division with neither bound is rejected client-side.
        await page.fill('#field-name', `Custom Age ${Date.now()}`);
        await page.fill('#field-startDate', '2026-11-01');
        await page.click('button[type="submit"]');
        await expect(page.getByText('Set a minimum or maximum age')).toBeVisible();
        await expect(page).toHaveURL(/\/admin\/create-tournament$/);

        // An inverted range is rejected too.
        await page.fill('#field-ageMin', '45');
        await page.fill('#field-ageMax', '30');
        await page.click('button[type="submit"]');
        await expect(page.getByText('Max age must be at least the min age.')).toBeVisible();
        await expect(page).toHaveURL(/\/admin\/create-tournament$/);

        // Switching back to a preset hides the range again.
        await page.locator('#field-ageGroup').selectOption('50+');
        await expect(range).toBeHidden();

        await logout(page);
    });

    test('a Mixed Doubles 50+ tournament shows both labels on the list and detail pages', async ({
        page,
    }) => {
        const name = `Mixed 50plus ${Date.now()}`;

        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-tournament');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-name', name);
        await page.fill('#field-startDate', '2026-11-01');
        await page.locator('#field-format').selectOption('mixed-doubles');
        await page.locator('#field-ageGroup').selectOption('50+');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/admin/tournaments', { timeout: 20_000 });

        const row = page.locator('.admin-league-item').filter({ hasText: name });
        await expect(row).toBeVisible();
        const rowMeta = row.getByTestId('tournament-meta');
        await expect(rowMeta).toContainText('Mixed Doubles');
        await expect(rowMeta).toContainText('50+');

        await row.click();
        await page.waitForURL('**/admin/tournament/**', { timeout: 15_000 });
        const meta = page.getByTestId('tournament-meta');
        await expect(meta).toContainText('Mixed Doubles');
        await expect(meta).toContainText('50+');
        // Mixed doubles rides the doubles paths, so the roster is teams, not players.
        await expect(page.getByText('Registered teams')).toBeVisible();

        await logout(page);
    });

    test('a custom age range round-trips to the listing', async ({ page }) => {
        const name = `Custom 30-45 ${Date.now()}`;

        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-tournament');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-name', name);
        await page.fill('#field-startDate', '2026-11-01');
        await page.locator('#field-ageGroup').selectOption('custom');
        await page.fill('#field-ageMin', '30');
        await page.fill('#field-ageMax', '45');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/admin/tournaments', { timeout: 20_000 });
        const row = page.locator('.admin-league-item').filter({ hasText: name });
        await expect(row.getByTestId('tournament-meta')).toContainText('30–45');

        await logout(page);
    });

    test('a Singles / Open tournament shows no age label and a players roster', async ({ page }) => {
        // The name deliberately avoids the word "Open" — the assertion below is
        // that an open division renders no age label at all.
        const name = `Singles AllAges ${Date.now()}`;

        await adminLogin(page, ADMIN_EMAIL, ADMIN_PASSWORD);
        await page.goto('/admin/create-tournament');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-name', name);
        await page.fill('#field-startDate', '2026-11-01');
        await page.locator('#field-format').selectOption('singles');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/admin/tournaments', { timeout: 20_000 });
        const rowMeta = page
            .locator('.admin-league-item')
            .filter({ hasText: name })
            .getByTestId('tournament-meta');
        await expect(rowMeta).toContainText('Singles');
        // Open divisions render no age label at all.
        await expect(rowMeta).not.toContainText('Open');

        await page.locator('.admin-league-item').filter({ hasText: name }).click();
        await page.waitForURL('**/admin/tournament/**', { timeout: 15_000 });
        await expect(page.getByText('Registered players')).toBeVisible();

        await logout(page);
    });
});
