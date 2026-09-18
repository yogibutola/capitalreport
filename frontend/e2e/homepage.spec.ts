import { test, expect } from '@playwright/test';

/**
 * Landing page (/) — no backend required except where noted.
 * Covers the redesigned homepage: nav, hero, count-up metrics, the interactive
 * Smart Slotting scheduler, demo CTAs and the mobile nav collapse.
 */
test.describe('Landing page', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForLoadState('networkidle');
    });

    test('renders nav, hero headline and CTAs', async ({ page }) => {
        const nav = page.locator('header.nav');
        await expect(nav).toBeVisible();
        for (const label of ['Leagues', 'Smart Slotting', 'Ratings', 'Tournaments']) {
            await expect(nav.locator('.nav__links').getByRole('link', { name: label })).toBeVisible();
        }
        await expect(nav.getByTestId('nav-player-signin')).toHaveAttribute('href', '/login');
        await expect(nav.getByTestId('nav-club-signin')).toBeVisible();
        await expect(nav.getByTestId('nav-club-signin')).toHaveAttribute('href', '/admin/login');
        await expect(nav.getByTestId('nav-book-demo')).toHaveAttribute('href', '/book-demo');

        const h1 = page.getByRole('heading', { level: 1 });
        await expect(h1).toContainText('Run the');
        await expect(h1).toContainText('Whole league');
        await expect(h1).toContainText('From one court.');

        await expect(page.getByTestId('hero-book-demo')).toBeVisible();
        await expect(page.getByRole('link', { name: 'Explore the platform' })).toBeVisible();
        // Social-proof row is hidden until there is a real customer count
        await expect(page.locator('.hero__proof')).toHaveCount(0);
        await expect(page.locator('section.hero')).not.toContainText('Trusted by');

        // Hero mockup: standings table with the leading team highlighted
        const standings = page.locator('table.standings');
        await expect(standings.locator('tbody tr')).toHaveCount(5);
        await expect(standings.locator('tr.is-lead')).toContainText('Dink Dynasty');
    });

    test('all four feature sections and the footer are present', async ({ page }) => {
        for (const id of ['leagues', 'slotting', 'ratings', 'tournaments']) {
            await expect(page.locator(`section#${id}`)).toHaveCount(1);
        }
        await expect(page.getByRole('heading', { level: 2, name: /Every division, standing, and schedule/ })).toBeVisible();
        await expect(page.locator('footer.footer')).toContainText('© 2026 StackedPaddle');
        await expect(page.locator('footer.footer').getByRole('link', { name: 'Club sign in' })).toHaveAttribute('href', '/admin/login');
    });

    test('metrics count up to their final values when scrolled into view', async ({ page }) => {
        const values = page.getByTestId('metric-value');
        await expect(values).toHaveCount(4);
        await values.first().scrollIntoViewIfNeeded();
        await expect(values.nth(0)).toHaveText('500+');
        await expect(values.nth(1)).toHaveText('18k');
        await expect(values.nth(2)).toHaveText('97%');
        await expect(values.nth(3)).toHaveText('4.9★');
    });

    test('Smart Slotting re-slot reshuffles pairings and keeps the status line', async ({ page }) => {
        const section = page.locator('section#slotting');
        await section.scrollIntoViewIfNeeded();

        const status = page.getByTestId('slotting-status');
        await expect(status).toHaveText(/18 players · 0 conflicts · balanced ±0\.15/);

        const cells = page.getByTestId('slot-cell');
        await expect(cells).toHaveCount(9);
        const before = await cells.allTextContents();

        // A shuffle can in theory reproduce the same layout; allow a couple of tries.
        let changed = false;
        for (let i = 0; i < 3 && !changed; i++) {
            await page.getByTestId('reslot-button').click();
            await page.waitForTimeout(300);
            const after = await cells.allTextContents();
            changed = after.join('|') !== before.join('|');
        }
        expect(changed).toBe(true);

        await expect(cells).toHaveCount(9);
        await expect(status).toHaveText(/18 players · 0 conflicts · balanced ±0\.15/);
        // At least one court is flagged as balanced after a re-slot
        expect(await page.locator('.sched__cell--balanced').count()).toBeGreaterThan(0);
    });

    test('"Book a demo" CTAs link to the booking page', async ({ page }) => {
        for (const id of ['hero-book-demo', 'cta-book-demo', 'footer-book-demo']) {
            await expect(page.getByTestId(id)).toHaveAttribute('href', '/book-demo');
        }
        await page.getByTestId('hero-book-demo').click();
        await page.waitForURL('**/book-demo', { timeout: 10_000 });
        await expect(page.getByRole('heading', { level: 1 })).toContainText('See your league');
    });

    test('"See it in a demo" starts the read-only club demo sign-in', async ({ page }) => {
        await page.locator('section#leagues').scrollIntoViewIfNeeded();
        const req = page.waitForRequest(
            r => r.url().includes('/api/v1/demo-signin') && r.method() === 'POST',
            { timeout: 10_000 }
        );
        await page.locator('section#leagues').getByRole('button', { name: /See it in a demo/ }).click();
        const request = await req;
        expect(request.postDataJSON()).toEqual({ persona: 'admin' });
    });

    test('"Tour a live club" starts the player demo sign-in', async ({ page }) => {
        await page.locator('section.cta').scrollIntoViewIfNeeded();
        const req = page.waitForRequest(
            r => r.url().includes('/api/v1/demo-signin') && r.method() === 'POST',
            { timeout: 10_000 }
        );
        await page.getByTestId('cta-tour-club').click();
        const request = await req;
        expect(request.postDataJSON()).toEqual({ persona: 'player' });
    });

    test('collapses the nav into a menu on phones with no horizontal scroll', async ({ page }) => {
        await page.setViewportSize({ width: 400, height: 800 });
        await page.reload();
        await page.waitForLoadState('networkidle');

        await expect(page.locator('.nav__links')).toBeHidden();
        await expect(page.getByTestId('nav-player-signin')).toBeHidden();
        await expect(page.getByTestId('nav-club-signin')).toBeHidden();

        const burger = page.getByRole('button', { name: 'Toggle menu' });
        await expect(burger).toBeVisible();
        await expect(burger).toHaveAttribute('aria-expanded', 'false');
        await burger.click();
        await expect(burger).toHaveAttribute('aria-expanded', 'true');
        await expect(page.locator('#landing-menu').getByRole('link', { name: 'Player sign in' })).toBeVisible();
        await expect(page.locator('#landing-menu').getByRole('link', { name: 'Club sign in' })).toBeVisible();

        const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth
        );
        expect(overflow).toBeLessThanOrEqual(0);
    });
});
