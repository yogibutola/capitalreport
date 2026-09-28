import { test, expect, Page } from '@playwright/test';
import { ALL_PLAYERS, adminLogin, playerLogin, logout, runSeeder } from './helpers';

const PASSWORD = 'Password@123';
const ADMIN_EMAIL = 'test_pro@gmail.com';

/**
 * The paddle bag on /profile, and the two read-only surfaces that show it:
 * the Find-a-Player result card and the club's league roster.
 *
 * Uses a player the search-filter spec doesn't touch, since that spec asserts on
 * exact result-set membership and these tests mutate a profile.
 *
 * Requires the backend + Mongo and the test_pro club (see e2e-seeded-specs setup).
 */

const OWNER = ALL_PLAYERS[8]; // pratibha.panwar@test.com
const OWNER_LAST = 'panwar';
const PROFILE_URL = /\/api\/v1\/profile/;

async function gotoProfile(page: Page) {
    await page.goto('/profile');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.profile-view')).toBeVisible();
}

async function startEdit(page: Page) {
    await page.getByRole('button', { name: /edit/i }).first().click();
    await expect(page.locator('form')).toBeVisible();
}

/** Save and wait for the PUT, so a follow-up read can't see a stale view. */
async function save(page: Page) {
    await Promise.all([
        page.waitForResponse((r) => PROFILE_URL.test(r.url()) && r.request().method() === 'PUT'),
        page.getByRole('button', { name: /save changes/i }).click(),
    ]);
    await expect(page.locator('.profile-view')).toBeVisible();
}

/** Fill paddle row `i` (0-based). Brand '' leaves the select untouched. */
async function fillRow(page: Page, i: number, brand: string, model?: string) {
    if (brand) await page.selectOption(`#field-paddleBrand${i + 1}`, brand);
    if (model !== undefined) await page.fill(`#field-paddleModel${i + 1}`, model);
}

async function addRow(page: Page) {
    await page.getByRole('button', { name: '+ Add a paddle' }).click();
}

/**
 * Remove every paddle row, then save. Leaves the profile with an empty bag.
 *
 * Always removes the *last* row: the rows are labelled by position, so dropping
 * row 1 renumbers the rest and detaches whatever element Playwright had already
 * resolved. Taking the last one leaves every earlier row's label untouched.
 */
async function clearPaddles(page: Page) {
    await gotoProfile(page);
    if ((await chips(page).count()) === 0) return; // already empty — skip the round-trip
    await startEdit(page);
    const remove = page.getByRole('button', { name: /^Remove paddle/ });
    for (let n = await remove.count(); n > 0; n--) {
        await remove.nth(n - 1).click();
        await expect(remove).toHaveCount(n - 1);
    }
    await save(page);
}

function chips(page: Page) {
    return page.locator('.profile-view .paddle-chip');
}

test.describe('Player paddles', () => {
    let leagueName: string;

    test.beforeAll(() => {
        leagueName = runSeeder();
    });

    test.beforeEach(async ({ page }) => {
        await playerLogin(page, OWNER, PASSWORD);
        await page.waitForLoadState('networkidle');
        await clearPaddles(page); // Each test starts from an empty bag.
    });

    test.afterEach(async ({ page }) => {
        await logout(page);
    });

    test('a paddle survives a save and a reload', async ({ page }) => {
        await startEdit(page);
        await addRow(page);
        await fillRow(page, 0, 'Joola', 'Perseus 16');
        await save(page);

        await expect(chips(page)).toHaveCount(1);
        await expect(chips(page).first()).toContainText('Joola');
        await expect(chips(page).first()).toContainText('Perseus 16');

        // Reload: proves it round-tripped to the server, not just local state.
        await gotoProfile(page);
        await expect(chips(page)).toHaveCount(1);
        await expect(chips(page).first()).toContainText('Perseus 16');
    });

    test('cancelling an edit discards the added row, twice over', async ({ page }) => {
        // Start from one saved paddle.
        await startEdit(page);
        await addRow(page);
        await fillRow(page, 0, 'Selkirk', 'Luxx');
        await save(page);
        await expect(chips(page)).toHaveCount(1);

        // First cancel.
        await startEdit(page);
        await addRow(page);
        await fillRow(page, 1, 'CRBN', '1X');
        await page.getByRole('button', { name: /^Cancel$/ }).click();
        await expect(chips(page)).toHaveCount(1);

        // Second cancel. This is the one that fails if snapshot/restore share an
        // array reference: the first cancel would have mutated the saved copy.
        await startEdit(page);
        await expect(page.locator('[id^="field-paddleBrand"]')).toHaveCount(1);
        await addRow(page);
        await fillRow(page, 1, 'Engage', '');
        await page.getByRole('button', { name: /^Cancel$/ }).click();
        await expect(chips(page)).toHaveCount(1);

        await startEdit(page);
        await expect(page.locator('[id^="field-paddleBrand"]')).toHaveCount(1);
    });

    test('removing every paddle clears the bag', async ({ page }) => {
        await startEdit(page);
        await addRow(page);
        await fillRow(page, 0, 'Paddletek', 'Bantam');
        await save(page);
        await expect(chips(page)).toHaveCount(1);

        await startEdit(page);
        await page.getByRole('button', { name: 'Remove paddle 1' }).click();
        await save(page);
        await expect(chips(page)).toHaveCount(0);

        // An empty list has to reach the backend, not be skipped as "unset".
        await gotoProfile(page);
        await expect(chips(page)).toHaveCount(0);
    });

    test('the add button disappears at three paddles', async ({ page }) => {
        await startEdit(page);
        const add = page.getByRole('button', { name: '+ Add a paddle' });

        for (const [i, brand] of ['Joola', 'Selkirk', 'CRBN'].entries()) {
            await add.click();
            await fillRow(page, i, brand, '');
        }
        await expect(add).toHaveCount(0);

        await save(page);
        await expect(chips(page)).toHaveCount(3);
    });

    test('an unlisted brand round-trips through "Other"', async ({ page }) => {
        await startEdit(page);
        await addRow(page);
        await page.selectOption('#field-paddleBrand1', 'Other');
        await page.fill('#field-paddleBrandOther1', 'Diadem');
        await page.fill('#field-paddleModel1', 'Warrior');
        await save(page);

        await expect(chips(page).first()).toContainText('Diadem');
        await expect(chips(page).first()).toContainText('Warrior');

        // Re-entering edit maps the stored brand back onto Other + free text.
        await startEdit(page);
        await expect(page.locator('#field-paddleBrand1')).toHaveValue('Other');
        await expect(page.locator('#field-paddleBrandOther1')).toHaveValue('Diadem');
    });

    test('a row with no brand is caught before the request is sent', async ({ page }) => {
        let requested = false;
        page.on('request', (r) => {
            if (PROFILE_URL.test(r.url()) && r.request().method() === 'PUT') requested = true;
        });

        await startEdit(page);
        await addRow(page);
        await page.fill('#field-paddleModel1', 'Perseus'); // model only, no brand
        await page.getByRole('button', { name: /save changes/i }).click();

        await expect(page.locator('app-form-summary')).toContainText('Paddle 1 brand');
        expect(requested, 'an incomplete paddle should not reach the backend').toBe(false);
    });

    test('paddles show on the Find-a-Player card', async ({ page }) => {
        await startEdit(page);
        await addRow(page);
        await fillRow(page, 0, 'Gearbox', 'CX14');
        await save(page);
        await logout(page);

        // A different player searches for them.
        await playerLogin(page, ALL_PLAYERS[0], PASSWORD);
        await page.waitForLoadState('networkidle');
        await page.fill('#search-last-name', OWNER_LAST);
        await Promise.all([
            page.waitForResponse((r) => /\/api\/v1\/players\/search/.test(r.url())),
            page.click('.search-actions button[type="submit"]'),
        ]);

        const row = page.locator('.search-result-item').filter({ hasText: OWNER });
        await expect(row.locator('.paddle-chip')).toContainText('Gearbox');
    });

    test('the club roster shows paddles added after registration', async ({ page }) => {
        // The seeder registers players into the league before any paddle exists,
        // so a roster reading its embedded player copy would show nothing here.
        await startEdit(page);
        await addRow(page);
        await fillRow(page, 0, 'Ronbus', 'R1');
        await save(page);
        await logout(page);

        await adminLogin(page, ADMIN_EMAIL, PASSWORD);
        await page.goto('/admin/leagues');
        await page.waitForSelector('text=' + leagueName, { timeout: 15_000 });
        await page.locator('.admin-league-item').filter({ hasText: leagueName }).click();
        await page.waitForURL('**/admin/league/**', { timeout: 15_000 });

        const row = page.locator('tbody tr').filter({ hasText: OWNER });
        await expect(row.locator('.paddle-chip')).toContainText('Ronbus');
    });
});
