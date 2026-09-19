import { test, expect, Page } from '@playwright/test';

/**
 * The light/dark theme toggle.
 *
 * The whole palette hangs off one `data-theme` attribute on <html>, so these
 * tests assert the attribute, the persisted choice, and — more importantly —
 * that real pixels actually change and stay readable. A toggle that flips the
 * attribute while the page stays dark would pass an attribute-only test.
 *
 * Only the last test needs a backend; it skips itself if the seeded read-only
 * demo account is unavailable.
 */

const STORAGE_KEY = 'sp-theme';

function theme(page: Page) {
  return page.locator('html').getAttribute('data-theme');
}

/**
 * The app is zoneless, so the effect that writes `data-theme` lands on the next
 * scheduled tick rather than inside the click handler. Every assertion about
 * the applied theme has to retry, or it races that tick.
 */
async function expectTheme(page: Page, expected: 'dark' | 'light') {
  await expect.poll(() => theme(page)).toBe(expected);
}

/** sRGB relative luminance, per WCAG. */
function luminance([r, g, b]: number[]) {
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function parseRgb(value: string): number[] {
  const nums = value.match(/[\d.]+/g);
  if (!nums) throw new Error(`unparseable colour: ${value}`);
  return nums.slice(0, 3).map(Number);
}

function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(parseRgb(a)), luminance(parseRgb(b))].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function colours(page: Page, selector: string) {
  return page.evaluate((sel) => {
    const el = sel === 'body' ? document.body : document.querySelector(sel)!;
    const s = getComputedStyle(el);
    return { bg: s.backgroundColor, fg: s.color };
  }, selector);
}

function bodyColours(page: Page) {
  return colours(page, 'body');
}

/**
 * Colour tokens are transitioned, so a sample taken straight after a toggle
 * catches a mid-cross-fade blend rather than the theme's real colours. Poll
 * until the contrast settles above the threshold.
 */
async function expectContrast(page: Page, selector: string, min: number) {
  await expect
    .poll(async () => {
      const { bg, fg } = await colours(page, selector);
      return contrast(fg, bg);
    })
    .toBeGreaterThan(min);
}

test.describe('theme toggle', () => {
  // Playwright's default emulated OS preference is light. Pin it to dark so
  // these tests start from the app's own default; the OS-preference test below
  // opens its own light context to cover the other branch.
  test.use({ colorScheme: 'dark' });

  test('defaults to dark and flips the whole page to light', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await expectTheme(page, 'dark');
    const dark = await bodyColours(page);
    expect(luminance(parseRgb(dark.bg))).toBeLessThan(0.1);

    await page.getByTestId('theme-toggle').first().click();

    await expectTheme(page, 'light');
    const light = await bodyColours(page);
    // The page really repaints — a light ground under dark ink.
    expect(luminance(parseRgb(light.bg))).toBeGreaterThan(0.6);
    expect(luminance(parseRgb(light.fg))).toBeLessThan(0.1);
  });

  test('keeps body text readable in both themes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await expectContrast(page, 'body', 4.5);

    await page.getByTestId('theme-toggle').first().click();

    await expectTheme(page, 'light');
    await expectContrast(page, 'body', 4.5);
  });

  test('keeps the brand accent readable as a button fill in light mode', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.getByTestId('theme-toggle').first().click();
    await expectTheme(page, 'light');

    // The lime brand colour is unreadable on a light page, so --ball and
    // --ball-ink deepen/lighten together. Verify the pair, not just the token.
    await expectContrast(page, '[data-testid="nav-book-demo"]', 4.5);
  });

  test('announces its state and toggles back', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const toggle = page.getByTestId('theme-toggle').first();
    await expect(toggle).toHaveAttribute('role', 'switch');
    await expect(toggle).toHaveAttribute('aria-checked', 'false');
    await expect(toggle).toHaveAttribute('aria-label', 'Switch to light theme');

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-checked', 'true');
    await expect(toggle).toHaveAttribute('aria-label', 'Switch to dark theme');

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-checked', 'false');
    await expectTheme(page, 'dark');
  });

  test('is reachable and operable by keyboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.getByTestId('theme-toggle').first().focus();
    await page.keyboard.press('Enter');

    await expectTheme(page, 'light');
  });

  test('remembers the choice across a reload and a navigation', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.getByTestId('theme-toggle').first().click();

    expect(await page.evaluate((k) => localStorage.getItem(k), STORAGE_KEY)).toBe('light');

    await page.reload();
    await page.waitForLoadState('networkidle');
    await expectTheme(page, 'light');

    // A page with no toggle of its own still honours the stored choice.
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await expectTheme(page, 'light');
  });

  test('applies the stored theme before first paint, with no dark flash', async ({ page }) => {
    await page.addInitScript(
      ([key, value]) => localStorage.setItem(key as string, value as string),
      [STORAGE_KEY, 'light']
    );

    await page.goto('/');
    // Sampled as early as the document exists — the inline script in index.html
    // must already have run, ahead of hydration.
    await expectTheme(page, 'light');
    await page.waitForLoadState('networkidle');
    await expectTheme(page, 'light');
  });

  test('honours the OS preference when the user has never chosen', async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: 'light' });
    const page = await context.newPage();

    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expectTheme(page, 'light');

    // An explicit choice wins over the OS from then on.
    await page.getByTestId('theme-toggle').first().click();
    await expectTheme(page, 'dark');
    await page.reload();
    await page.waitForLoadState('networkidle');
    await expectTheme(page, 'dark');

    await context.close();
  });

  test('is available in the signed-in app header', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const signedIn = page
      .waitForURL((url) => /\/(player|league)/.test(url.pathname), { timeout: 15_000 })
      .then(() => true)
      .catch(() => false);

    await page.locator('section.cta').scrollIntoViewIfNeeded();
    await page.getByTestId('cta-tour-club').click();

    test.skip(!(await signedIn), 'demo sign-in unavailable — backend or demo seed missing');

    const toggle = page.locator('header.global-header').getByTestId('theme-toggle');
    await expect(toggle).toBeVisible();

    await toggle.click();
    await expectTheme(page, 'light');

    // The signed-in chrome repaints too, and its nav stays legible.
    await expect
      .poll(async () => {
        const { bg, fg } = await page.locator('.nav-tab-link').first().evaluate((el) => {
          const header = getComputedStyle(el.closest('header')!).backgroundColor;
          return { bg: header, fg: getComputedStyle(el).color };
        });
        return luminance(parseRgb(bg)) > 0.5 && contrast(fg, bg) > 3;
      })
      .toBe(true);
  });
});

/**
 * The palette is entirely `var(--token)` references. A typo'd token name
 * resolves to nothing and CSS silently drops the whole declaration — no error,
 * just a missing colour — so assert that every referenced custom property has a
 * value in both themes.
 */
for (const mode of ['dark', 'light'] as const) {
  test(`every referenced custom property resolves in ${mode}`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('sp-theme', t as string), mode);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const missing = await page.evaluate(() => {
      const referenced = new Set<string>();
      const defined = new Set<string>();

      const walk = (rules: CSSRuleList) => {
        for (const rule of Array.from(rules) as Array<CSSRule & { cssRules?: CSSRuleList; style?: CSSStyleDeclaration }>) {
          if (rule.cssRules) walk(rule.cssRules);
          if (!rule.style) continue;
          for (const prop of Array.from(rule.style)) {
            if (prop.startsWith('--')) defined.add(prop);
            for (const m of rule.style.getPropertyValue(prop).matchAll(/var\(\s*(--[\w-]+)/g)) {
              referenced.add(m[1]);
            }
          }
        }
      };

      for (const sheet of Array.from(document.styleSheets)) {
        try {
          walk(sheet.cssRules);
        } catch {
          // Cross-origin sheet (the Google Fonts import) — nothing of ours in it.
        }
      }

      const root = getComputedStyle(document.documentElement);
      return [...referenced]
        .filter((name) => !defined.has(name) && root.getPropertyValue(name).trim() === '')
        .sort();
    });

    expect(missing, `unresolved custom properties in ${mode} theme`).toEqual([]);
  });
}
