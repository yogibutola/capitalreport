import { test, expect, Page } from '@playwright/test';

/**
 * The StackedPaddle wordmark: one line, every letter the same size, light
 * wide-tracked STACKED running straight into bold compact PADDLE with no word
 * gap. Rendered by the shared <app-brand-logo> component so every page shows
 * the same mark.
 *
 * Only the last test needs a backend (it uses the seeded read-only demo account
 * to reach the signed-in header); it skips itself if demo sign-in is unavailable.
 */

/** Pages that render the mark and need no backend. */
const PUBLIC_PAGES: Array<{ path: string; where: string }> = [
    { path: '/', where: 'header.nav' },
    { path: '/', where: 'footer.footer' },
    { path: '/book-demo', where: 'header.nav' },
    { path: '/login', where: '.card' },
    { path: '/signup', where: '.card' },
    { path: '/admin/login', where: '.card' },
    { path: '/admin/signup', where: '.card' },
    { path: '/forgot-password', where: '.card' },
    { path: '/reset-password', where: '.card' },
    { path: '/x9k2-console/login', where: '.card' },
];

/** Asserts the single-line light-over-bold construction of one rendered mark. */
async function expectWordmark(page: Page, markSelector: string) {
    const mark = page.locator(markSelector).first();
    await expect(mark).toBeVisible();

    // Tracking is CSS letter-spacing, so the DOM keeps real words for screen
    // readers and copy/paste; the uppercase is presentational.
    await expect(mark.locator('.brand__top')).toHaveText('Stacked');
    await expect(mark.locator('.brand__bottom')).toHaveText('Paddle');
    await expect(mark.locator('.brand__bottom')).toHaveCSS('text-transform', 'uppercase');

    const top = await mark.locator('.brand__top').boundingBox();
    const bottom = await mark.locator('.brand__bottom').boundingBox();
    expect(top).not.toBeNull();
    expect(bottom).not.toBeNull();

    const style = await mark.evaluate((el) => {
        const t = getComputedStyle(el.querySelector('.brand__top')!);
        const b = getComputedStyle(el.querySelector('.brand__bottom')!);
        return {
            topWeight: Number(t.fontWeight),
            bottomWeight: Number(b.fontWeight),
            topTracking: parseFloat(t.letterSpacing),
            bottomTracking: parseFloat(b.letterSpacing) || 0,
            topSize: parseFloat(t.fontSize),
            bottomSize: parseFloat(b.fontSize),
        };
    });

    // Every letter is set at the same size.
    expect(Math.abs(style.topSize - style.bottomSize)).toBeLessThan(0.51);

    // One line, and PADDLE butts straight onto the D with no word gap. The top
    // box carries a trailing letter-space, so strip that to find the D's edge.
    const dEdge = top!.x + top!.width - style.topTracking;
    expect(Math.abs(bottom!.x - dEdge)).toBeLessThan(2);
    expect(Math.abs(top!.y + top!.height - (bottom!.y + bottom!.height))).toBeLessThan(3);

    // Light and wide-tracked against bold and compact.
    expect(style.topWeight).toBeLessThanOrEqual(300);
    expect(style.bottomWeight).toBeGreaterThanOrEqual(700);
    expect(style.topTracking).toBeGreaterThan(style.bottomTracking);

    // Announced once, as a mark rather than as two stray words.
    await expect(mark.locator('.brand')).toHaveAttribute('role', 'img');
    await expect(mark.locator('.brand')).toHaveAttribute('aria-label', /StackedPaddle/);
}

for (const { path, where } of PUBLIC_PAGES) {
    test(`wordmark renders in ${where} on ${path}`, async ({ page }) => {
        await page.goto(path);
        await page.waitForLoadState('networkidle');
        await expectWordmark(page, `${where} app-brand-logo`);
    });
}

/**
 * The one-line mark is much wider than the old text logo, so the public navs
 * have to keep their controls on screen next to it.
 */
for (const path of ['/', '/book-demo']) {
    test(`wordmark leaves the nav controls on screen at 360px on ${path}`, async ({ page }) => {
        await page.setViewportSize({ width: 360, height: 800 });
        await page.goto(path);
        await page.waitForLoadState('networkidle');

        const rightMost = await page.locator('header.nav').first().evaluate((header) => {
            let max = 0;
            header.querySelectorAll('*').forEach((node) => {
                const box = node.getBoundingClientRect();
                if (box.width && box.height) max = Math.max(max, box.right);
            });
            return max;
        });
        expect(rightMost).toBeLessThanOrEqual(360);
    });
}

test('the same wordmark is used in the signed-in app header', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const signedIn = page
        .waitForURL((url) => /\/(player|league)/.test(url.pathname), { timeout: 15_000 })
        .then(() => true)
        .catch(() => false);

    await page.locator('section.cta').scrollIntoViewIfNeeded();
    await page.getByTestId('cta-tour-club').click();

    test.skip(!(await signedIn), 'demo sign-in unavailable — backend or demo seed missing');

    await expectWordmark(page, 'header.global-header .header-brand-logo app-brand-logo');
});
