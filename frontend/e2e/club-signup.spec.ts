import { test, expect } from '@playwright/test';
import { adminLogin } from './helpers';

/**
 * Clubs are their own records, run by a person's account. Two ways in:
 *  - a visitor signs up as the organiser and creates the club in one step;
 *  - an existing player creates a club from their profile.
 * Either way the session becomes the club's admin. Requires backend + Mongo.
 */
const PASSWORD = 'Password@123';

test.describe('Club signup', () => {
    test('a visitor signs up as organiser and lands in their club admin', async ({ page }) => {
        const email = `organiser.${Date.now()}@test.com`;
        await page.goto('/admin/signup');
        await page.waitForLoadState('networkidle');

        await page.fill('#field-firstName', 'Olive');
        await page.fill('#field-lastName', 'Organiser');
        await page.fill('#field-clubName', `Olive's Ladder Club ${Date.now()}`);
        await page.fill('#field-email', email);
        await page.fill('#field-address', '1 Baseline Ct');
        await page.fill('#field-phone', '555-0100');
        await page.fill('#field-password', PASSWORD);
        await page.click('button[type="submit"]');
        await page.waitForURL('**/admin/season', { timeout: 20_000 });

        // Signing back in derives the admin role from owning the club.
        await page.evaluate(() => localStorage.removeItem('pickleball_user'));
        await adminLogin(page, email, PASSWORD);
        await expect(page).toHaveURL(/\/admin\/season/);
    });

    test('the organiser name is required', async ({ page }) => {
        await page.goto('/admin/signup');
        await page.waitForLoadState('networkidle');
        await page.fill('#field-clubName', 'Nameless Club');
        await page.fill('#field-email', `nameless.${Date.now()}@test.com`);
        await page.fill('#field-address', '1 Court St');
        await page.fill('#field-phone', '555-0100');
        await page.fill('#field-password', PASSWORD);
        await page.click('button[type="submit"]');
        await expect(page.locator('#field-firstName')).toHaveAttribute('aria-invalid', 'true');
        await expect(page).toHaveURL(/\/admin\/signup/);
    });

    test('an existing player creates a club from their profile', async ({ page }) => {
        const email = `player.club.${Date.now()}@test.com`;

        // Plain player signup through the API, then adopt the session like the app does.
        const resp = await page.request.post('/api/v1/signup', {
            data: { firstName: 'Pia', lastName: 'Player', email, password: PASSWORD, dupr_rating: 3.5 },
        });
        expect(resp.status()).toBe(201);
        const body = await resp.json();
        await page.goto('/');
        await page.evaluate((user) => localStorage.setItem('pickleball_user', JSON.stringify(user)), {
            id: body.id, firstName: 'Pia', lastName: 'Player', userName: '', email,
            dupr_rating: 3.5, role: 'player', token: body.token,
        });

        await page.goto('/profile');
        await page.click('[data-testid="create-club-link"]');
        await page.waitForURL('**/admin/signup');

        // Already signed in: only the club details are asked for.
        await expect(page.locator('#field-email')).toHaveCount(0);
        await expect(page.locator('#field-password')).toHaveCount(0);
        await page.fill('#field-clubName', `Pia's Paddle Club ${Date.now()}`);
        await page.fill('#field-address', '9 Kitchen Ln');
        await page.fill('#field-phone', '555-0199');
        await page.click('button:has-text("Create Club")');
        await page.waitForURL('**/admin/season', { timeout: 20_000 });

        const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('pickleball_user') || '{}'));
        expect(stored.role).toBe('admin');

        // Coming back to the signup page now says they already run a club.
        await page.goto('/admin/signup');
        await expect(page.locator('[data-testid="already-runs-club"]')).toBeVisible();
    });
});
