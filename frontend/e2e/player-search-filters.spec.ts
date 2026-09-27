import { test, expect, Page } from '@playwright/test';
import { ALL_PLAYERS, playerLogin, logout, runSeeder } from './helpers';
import { PHONE, expectNoHorizontalOverflow, expectStacked } from './mobile-helpers';

const PASSWORD = 'Password@123';

/**
 * The DUPR-range and distance filters on "Find a Player" (player home, /league).
 *
 * The seeder gives every test player a Northern-Virginia ZIP, ordered
 * nearest-to-farthest from Ashburn 20147 (see PLAYER_ZIPS in test_data_seeder.py):
 * Ashburn 0, Sterling 4.5, Herndon 7.1, Reston 10.0, Leesburg 10.4,
 * Centreville 15.1, Fairfax 15.7, Alexandria 28.0, Baltimore 49.1.
 *
 * So a 20-mile radius from 20147 includes the first seven and excludes the last
 * two — which is what makes "narrowing the radius drops players" assertable.
 * Requires the backend + Mongo and the test_pro club (see e2e-seeded-specs setup).
 */

const SEARCH_URL = /\/api\/v1\/players\/search/;

/** Click Search without waiting — for the cases that must NOT reach the server. */
async function submit(page: Page) {
    await page.click('.search-actions button[type="submit"]');
}

/** Submit and wait for the response, so a follow-up read can't see stale results. */
async function search(page: Page) {
    await Promise.all([
        page.waitForResponse((r) => SEARCH_URL.test(r.url())),
        submit(page),
    ]);
}

async function resultEmails(page: Page): Promise<string[]> {
    await expect(page.locator('.search-results-list')).toBeVisible();
    return page.locator('.search-result-item .player-email').allTextContents();
}

test.describe('Find a Player: DUPR range and distance', () => {
    test.beforeAll(() => {
        runSeeder();
    });

    test.beforeEach(async ({ page }) => {
        await playerLogin(page, ALL_PLAYERS[0], PASSWORD);
        await page.waitForLoadState('networkidle');
    });

    test.afterEach(async ({ page }) => {
        await logout(page);
    });

    test('an inverted DUPR range is rejected without hitting the server', async ({ page }) => {
        let requested = false;
        page.on('request', (r) => {
            if (SEARCH_URL.test(r.url())) requested = true;
        });

        await page.fill('#search-dupr-min', '4.5');
        await page.fill('#search-dupr-max', '3.0');
        await submit(page);

        await expect(page.getByText('Max rating must be at least the min rating.')).toBeVisible();
        expect(requested, 'an invalid range should not reach the backend').toBe(false);

        // Correcting it clears the message and lets the search through.
        await page.fill('#search-dupr-max', '5.0');
        await expect(
            page.getByText('Max rating must be at least the min rating.')
        ).toBeHidden();
    });

    test('a DUPR-range search sends the bounds and every result sits inside them', async ({
        page,
    }) => {
        await page.fill('#search-dupr-min', '3.3');
        await page.fill('#search-dupr-max', '3.7');

        const [request] = await Promise.all([
            page.waitForRequest(SEARCH_URL),
            search(page),
        ]);

        const params = new URL(request.url()).searchParams;
        expect(params.get('dupr_min')).toBe('3.3');
        expect(params.get('dupr_max')).toBe('3.7');

        await expect(page.locator('.search-results-list')).toBeVisible();
        const ratings = await page.locator('.search-result-item .rating-value').allTextContents();
        expect(ratings.length).toBeGreaterThan(0);
        for (const raw of ratings) {
            const value = Number(raw.trim());
            expect(value).toBeGreaterThanOrEqual(3.3);
            expect(value).toBeLessThanOrEqual(3.7);
        }
        // No radius was asked for, so no distance is claimed.
        await expect(page.locator('.player-distance-badge')).toHaveCount(0);
    });

    test('a radius search shows a distance on every row and excludes the far players', async ({
        page,
    }) => {
        await page.fill('#search-radius', '20');
        await page.fill('#search-zip', '20147');
        await search(page);

        const emails = await resultEmails(page);
        expect(emails.length).toBeGreaterThan(0);

        // Every row is badged with its distance, and all are inside the radius.
        const rows = page.locator('.search-result-item');
        await expect(page.locator('.player-distance-badge')).toHaveCount(await rows.count());
        const miles = await page.locator('.player-distance-badge .rating-value').allTextContents();
        for (const raw of miles) {
            expect(Number(raw.trim())).toBeLessThanOrEqual(20);
        }

        // Baltimore (49mi) and Alexandria (28mi) are outside 20 miles.
        expect(emails).not.toContain('pratibha.panwar@test.com');
        expect(emails).not.toContain('deepak.panwar@test.com');

        // The applied radius is stated alongside the count.
        await expect(page.locator('.search-results-header')).toContainText('within 20 mi');
    });

    test('narrowing the radius drops the players that are further out', async ({ page }) => {
        await page.fill('#search-zip', '20147');

        await page.fill('#search-radius', '50');
        await search(page);
        const wide = await resultEmails(page);

        await page.fill('#search-radius', '6');
        await search(page);
        const narrow = await resultEmails(page);

        // Asserted by membership, not by count: the database accumulates players
        // across runs, so only these specific distances are stable.
        // Herndon is 7.1mi -> inside 50, outside 6. Sterling is 4.5mi -> inside both.
        expect(wide).toContain('aditya.butola@test.com');
        expect(narrow).not.toContain('aditya.butola@test.com');
        expect(wide).toContain('usha.b@test.com');
        expect(narrow).toContain('usha.b@test.com');
    });

    test('the searcher never appears in their own results', async ({ page }) => {
        await page.fill('#search-radius', '500');
        await page.fill('#search-zip', '20147');
        await search(page);

        expect(await resultEmails(page)).not.toContain(ALL_PLAYERS[0]);
    });

    test('an unrecognised ZIP is reported next to the ZIP field', async ({ page }) => {
        await page.fill('#search-radius', '25');
        await page.fill('#search-zip', '00000');
        await search(page);

        await expect(page.locator('.search-hint')).toContainText("don't recognise that ZIP");
        await expect(page.locator('.search-results-list')).toHaveCount(0);
        // The hint offers the profile as the place to fix it for good.
        await expect(page.locator('.search-hint a')).toHaveAttribute('href', '/profile');
    });

    test('the ZIP box is prefilled from the profile so distance works out of the box', async ({
        page,
    }) => {
        // The seeder gives this player Ashburn 20147. Signing in rebuilds the cached
        // user from a response that carries no ZIP, so the dashboard falls back to
        // fetching the profile - either way the box shows their home ZIP.
        await expect(page.locator('#search-zip')).toHaveValue('20147');

        await page.fill('#search-radius', '20');
        await search(page);
        await expect(page.locator('.player-distance-badge').first()).toBeVisible();
    });

    test('name and DUPR filters combine with the radius', async ({ page }) => {
        await page.fill('#search-last-name', 'Butola');
        await page.fill('#search-dupr-min', '3.0');
        await page.fill('#search-radius', '20');
        await page.fill('#search-zip', '20147');

        const [request] = await Promise.all([
            page.waitForRequest(SEARCH_URL),
            search(page),
        ]);
        const params = new URL(request.url()).searchParams;
        expect(params.get('last_name')).toBe('Butola');
        expect(Number(params.get('dupr_min'))).toBe(3.0);
        expect(Number(params.get('radius_miles'))).toBe(20);

        for (const name of await page.locator('.search-result-item .player-name').allTextContents()) {
            expect(name).toContain('Butola');
        }
    });

    test('Clear empties the filters and the results but keeps the home ZIP', async ({ page }) => {
        await page.fill('#search-first-name', 'a');
        await page.fill('#search-dupr-min', '3.0');
        await page.fill('#search-dupr-max', '4.0');
        await page.fill('#search-radius', '25');
        await search(page);
        await expect(page.locator('.search-results-header')).toBeVisible();

        await page.click('.search-actions button:has-text("Clear")');

        await expect(page.locator('#search-first-name')).toHaveValue('');
        await expect(page.locator('#search-dupr-min')).toHaveValue('');
        await expect(page.locator('#search-dupr-max')).toHaveValue('');
        await expect(page.locator('#search-radius')).toHaveValue('');
        await expect(page.locator('.search-results-list')).toHaveCount(0);
        // Their own ZIP isn't part of the query - it's where they live.
        await expect(page.locator('#search-zip')).toHaveValue('20147');
    });

    test('an empty form does not dump the whole roster', async ({ page }) => {
        let requested = false;
        page.on('request', (r) => {
            if (SEARCH_URL.test(r.url())) requested = true;
        });

        await submit(page);

        expect(requested, 'a filterless search should not be sent').toBe(false);
        await expect(page.locator('.search-results-list')).toHaveCount(0);
    });
});

test.describe('Find a Player: a brand-new account', () => {
    test('a ZIP given at signup makes distance search work immediately', async ({ page }) => {
        // The cold-start path: without location at signup, a new player would be
        // invisible to distance search until they went and edited their profile.
        const email = `zipper.${Date.now()}@test.com`;

        await page.goto('/signup');
        await page.waitForLoadState('networkidle');
        await page.fill('#field-firstName', 'Zip');
        await page.fill('#field-lastName', 'Perton');
        await page.fill('#field-email', email);
        await page.fill('#field-password', 'Password@123');
        await page.fill('#field-dupr_rating', '3.5');
        await page.fill('#field-city', 'Ashburn');
        await page.fill('#field-state', 'VA');
        await page.fill('#field-zip_code', '20147');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/league', { timeout: 20_000 });

        // Straight to a radius search - never visited /profile.
        await expect(page.locator('#search-zip')).toHaveValue('20147');
        await page.fill('#search-radius', '20');
        await page.click('.search-actions button[type="submit"]');

        await expect(page.locator('.player-distance-badge').first()).toBeVisible();
        await expect(page.locator('.search-results-header')).toContainText('within 20 mi');

        await logout(page);
    });

    test('signup still succeeds with the location row left blank', async ({ page }) => {
        const email = `nozip.${Date.now()}@test.com`;

        await page.goto('/signup');
        await page.waitForLoadState('networkidle');
        await page.fill('#field-firstName', 'No');
        await page.fill('#field-lastName', 'Zipper');
        await page.fill('#field-email', email);
        await page.fill('#field-password', 'Password@123');
        await page.fill('#field-dupr_rating', '3.5');
        await page.click('button[type="submit"]');

        await page.waitForURL('**/league', { timeout: 20_000 });

        // Name search works; a radius search explains what's missing.
        await page.fill('#search-radius', '25');
        await page.click('.search-actions button[type="submit"]');
        await expect(page.locator('.search-hint')).toContainText('ZIP code');

        await logout(page);
    });

    test('a malformed ZIP is rejected at signup', async ({ page }) => {
        await page.goto('/signup');
        await page.waitForLoadState('networkidle');
        await page.fill('#field-firstName', 'Bad');
        await page.fill('#field-lastName', 'Zip');
        await page.fill('#field-email', `badzip.${Date.now()}@test.com`);
        await page.fill('#field-password', 'Password@123');
        await page.fill('#field-dupr_rating', '3.5');
        await page.fill('#field-zip_code', '123');
        await page.click('button[type="submit"]');

        await expect(page.locator('p#err-zip_code')).toContainText('ZIP');
        await expect(page).toHaveURL(/\/signup$/);
    });
});

test.describe('Find a Player at 390px', () => {
    test.use({ viewport: PHONE });

    test('the filter fields stack and nothing overflows', async ({ page }) => {
        await playerLogin(page, ALL_PLAYERS[0], PASSWORD);
        await page.waitForLoadState('networkidle');

        await expectNoHorizontalOverflow(page, 'player home with search filters');
        // The 6-up filter grid must collapse to one column, not scroll sideways.
        await expectStacked(page, '#search-first-name', '#search-last-name', 'search filters');
        await expectStacked(page, '#search-dupr-max', '#search-radius', 'search filters');
        await expectStacked(page, '#search-radius', '#search-zip', 'search filters');

        await logout(page);
    });
});
