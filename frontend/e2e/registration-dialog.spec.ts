import { test, expect, Page } from '@playwright/test';
import { ALL_PLAYERS, playerLogin } from './helpers';

const PASSWORD = 'Password@123';
const PLAYER = ALL_PLAYERS[0];

/**
 * Registering for a league or tournament reports the server's response in a
 * dialog the player has to dismiss (success and failure alike).
 *
 * Sign-in hits the real backend; the available-events lists and the register
 * POSTs are stubbed with page.route, so no seeded leagues/tournaments are needed.
 */

const LEAGUE = {
    id: 'e2e-reg-dialog-league',
    league_name: 'Dialog Test League',
    status: 'active',
    league_start_date: '2026-01-01',
    league_end_date: '2026-12-31',
};

const SINGLES = {
    tournament_id: 'e2e-reg-dialog-singles',
    tournament_name: 'Dialog Singles Open',
    tournament_status: 'pending',
    tournament_start_date: '12-01-2026',
    match_format: 'singles',
    player_count: 0,
};

const DOUBLES = {
    tournament_id: 'e2e-reg-dialog-doubles',
    tournament_name: 'Dialog Doubles Cup',
    tournament_status: 'pending',
    tournament_start_date: '12-02-2026',
    match_format: 'doubles',
    player_count: 0,
};

type Outcome = { ok: true; message: string } | { ok: false; detail: string };

async function stubRegister(page: Page, urlGlob: string, outcome: Outcome) {
    await page.route(urlGlob, (route) => {
        if (route.request().method() !== 'POST') return route.fallback();
        return outcome.ok
            ? route.fulfill({ status: 200, json: { message: outcome.message } })
            : route.fulfill({ status: 400, json: { detail: outcome.detail } });
    });
}

function dialog(page: Page) {
    return page.locator('.confirm-dialog');
}

/** Click Register, then accept the "Register for this …?" confirmation. */
async function registerAndConfirm(page: Page, register: ReturnType<Page['getByRole']>) {
    await register.click();
    await expect(dialog(page)).toContainText('Register for this');
    await dialog(page).getByRole('button', { name: 'Register' }).click();
}

test.describe('Registration result dialog', () => {
    test.beforeEach(async ({ page }) => {
        await page.route('**/api/v1/all_leagues', (route) => route.fulfill({ json: [LEAGUE] }));
        await page.route('**/api/v1/all_tournaments', (route) =>
            route.fulfill({ json: [SINGLES, DOUBLES] })
        );
        await playerLogin(page, PLAYER, PASSWORD);
    });

    test('league success shows the server message in a dialog', async ({ page }) => {
        await stubRegister(page, '**/api/v1/league/register', {
            ok: true,
            message: 'Player registered successfully',
        });
        await page.goto('/player/leagues?tab=available');

        const row = page.locator('tr', { hasText: LEAGUE.league_name });
        await registerAndConfirm(page, row.getByRole('button', { name: 'Register' }));

        await expect(page.getByRole('dialog')).toBeVisible();
        await expect(dialog(page)).toContainText(`You're registered for ${LEAGUE.league_name}!`);
        await expect(dialog(page)).toContainText('Player registered successfully');
        await expect(dialog(page).getByRole('button')).toHaveCount(1);

        await dialog(page).getByRole('button', { name: 'OK' }).click();
        await expect(dialog(page)).toHaveCount(0);
    });

    test('league failure shows the backend detail in a dialog', async ({ page }) => {
        await stubRegister(page, '**/api/v1/league/register', {
            ok: false,
            detail: "Your DUPR rating is outside this league's range",
        });
        await page.goto('/player/leagues?tab=available');

        const row = page.locator('tr', { hasText: LEAGUE.league_name });
        await registerAndConfirm(page, row.getByRole('button', { name: 'Register' }));

        await expect(page.getByRole('alertdialog')).toBeVisible();
        await expect(dialog(page)).toContainText(`Couldn't register for ${LEAGUE.league_name}`);
        await expect(dialog(page)).toContainText("Your DUPR rating is outside this league's range.");

        await page.keyboard.press('Escape');
        await expect(dialog(page)).toHaveCount(0);
    });

    test('singles tournament success and failure both open the dialog', async ({ page }) => {
        await stubRegister(page, '**/api/v1/tournament/register', {
            ok: true,
            message: 'Player registered successfully',
        });
        await page.goto('/player/tournaments?tab=available');

        const card = page.locator('.tournament-card', { hasText: SINGLES.tournament_name });
        await registerAndConfirm(page, card.getByRole('button', { name: 'Register' }));
        await expect(dialog(page)).toContainText(`You're registered for ${SINGLES.tournament_name}!`);
        await expect(dialog(page)).toContainText('Player registered successfully');
        await dialog(page).getByRole('button', { name: 'OK' }).click();

        await page.unroute('**/api/v1/tournament/register');
        await stubRegister(page, '**/api/v1/tournament/register', {
            ok: false,
            detail: 'Registration is closed for this tournament',
        });
        await registerAndConfirm(page, card.getByRole('button', { name: 'Register' }));
        await expect(dialog(page)).toContainText(`Couldn't register for ${SINGLES.tournament_name}`);
        await expect(dialog(page)).toContainText('Registration is closed for this tournament.');
    });

    test('doubles panel registration opens the dialog', async ({ page }) => {
        await stubRegister(page, '**/api/v1/tournament/register', {
            ok: true,
            message: 'Player registered successfully',
        });
        await page.goto('/player/tournaments?tab=available');

        const card = page.locator('.tournament-card', { hasText: DOUBLES.tournament_name });
        await card.getByRole('button', { name: 'Register' }).click();
        // Default partner mode is "looking for a partner", so no extra input is needed.
        await card.getByRole('button', { name: 'Confirm registration' }).click();

        await expect(dialog(page)).toContainText(`You're registered for ${DOUBLES.tournament_name}!`);
        await expect(dialog(page)).toContainText('Player registered successfully');
        await expect(card.locator('.register-panel')).toHaveCount(0);
    });
});
