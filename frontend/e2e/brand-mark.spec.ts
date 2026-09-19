import { test, expect } from '@playwright/test';

/**
 * The StackedPaddle icon (<app-brand-mark>) must appear on every page, so the
 * brand is never just a wordmark. These are the pages reachable without a
 * session; the signed-in header's copy is asserted in the seeded flows.
 *
 * No backend required — each of these renders its shell client-side.
 */
const PUBLIC_PAGES = [
  '/',
  '/book-demo',
  '/login',
  '/signup',
  '/forgot-password',
  '/reset-password',
  '/admin/login',
  '/admin/signup',
  '/x9k2-console/login',
];

test.describe('Brand mark', () => {
  for (const path of PUBLIC_PAGES) {
    test(`is visible on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');

      const mark = page.locator('app-brand-mark').first();
      await expect(mark).toBeVisible();
      // The paddle glyph, not just an empty tile.
      await expect(mark.locator('svg ellipse')).toBeVisible();
      await expect(mark.locator('svg rect')).toBeVisible();
    });
  }

  test('is the same glyph in the landing nav and the footer', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const marks = page.locator('app-brand-mark');
    await expect(marks).toHaveCount(2);

    const shapes = await marks.evaluateAll((els) =>
      els.map((el) => el.querySelector('svg')!.innerHTML.replace(/\s+/g, ' ').trim()),
    );
    expect(shapes[0]).toBe(shapes[1]);
  });

  test('tile keeps painting in both themes', async ({ page }) => {
    // Pin the starting theme so one click is always dark → light, whatever the
    // runner's prefers-color-scheme says.
    await page.addInitScript(() => localStorage.setItem('sp-theme', 'dark'));
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect.poll(() => page.locator('html').getAttribute('data-theme')).toBe('dark');

    const tileColors = async () =>
      page.locator('app-brand-mark .mark').first().evaluate((el) => {
        const s = getComputedStyle(el);
        return { background: s.backgroundColor, color: s.color };
      });

    const dark = await tileColors();
    expect(dark.background).not.toBe('rgba(0, 0, 0, 0)');
    expect(dark.color).not.toBe(dark.background);

    // Zoneless: data-theme lands on the next tick, so poll rather than read once.
    await page.getByTestId('theme-toggle').first().click();
    await expect
      .poll(() => page.locator('html').getAttribute('data-theme'))
      .toBe('light');

    const light = await tileColors();
    expect(light.background).not.toBe('rgba(0, 0, 0, 0)');
    expect(light.color).not.toBe(light.background);
    // The lime deepens to olive in light, so the tile must not be identical.
    expect(light.background).not.toBe(dark.background);
  });
});
