import { test, expect, Page } from '@playwright/test';
import {
    PHONE,
    expectNoHorizontalOverflow,
    expectStacked,
    expectTappable,
} from './mobile-helpers';

/**
 * Mobile layout guard.
 *
 * The app was built desktop-first, so the failure mode this file exists to catch
 * is a page that pushes itself wider than the phone — a fixed-width input, a bare
 * table, a flex row with no wrap. Every assertion here runs at one phone width.
 * The assertions themselves live in ./mobile-helpers so the platform-console spec
 * can reuse them (Playwright forbids importing one spec from another).
 */

// ─── Public routes: no seeding, no sign-in ───────────────────────────────────

test.describe('mobile layout at 390px — public routes', () => {
    test.use({ viewport: PHONE });

    const PUBLIC_ROUTES = [
        { path: '/', name: 'landing' },
        { path: '/login', name: 'player sign in' },
        { path: '/signup', name: 'player sign up' },
        { path: '/admin/login', name: 'club sign in' },
        { path: '/admin/signup', name: 'club sign up' },
        { path: '/forgot-password', name: 'forgot password' },
        { path: '/book-demo', name: 'book a demo' },
        { path: '/x9k2-console/login', name: 'platform sign in' },
    ];

    for (const route of PUBLIC_ROUTES) {
        test(`${route.name} has no horizontal overflow`, async ({ page }) => {
            await page.goto(route.path);
            await page.waitForLoadState('networkidle');
            await expectNoHorizontalOverflow(page, route.name);
        });
    }

    test('sign-up name fields stack instead of sitting in a 2-up grid', async ({ page }) => {
        await page.goto('/signup');
        await page.waitForLoadState('networkidle');
        await expectStacked(page, '#field-firstName', '#field-lastName', 'signup name grid');
    });

    test('sign-in submit button stays on screen', async ({ page }) => {
        await page.goto('/login');
        await page.waitForLoadState('networkidle');
        await expectTappable(page, 'button[type="submit"]', 'sign in button');
    });
});

// ─── Signed-in routes, via the read-only demo session ────────────────────────
//
// seed_demo.py creates the demo club, league and tournament; /api/v1/demo-signin
// mints a session for them in one call. Demo tokens are read-only server-side, so
// this sweep cannot mutate anything. If the demo data is absent the block skips,
// which keeps the public tests above as the gate on a bare checkout.

test.describe('mobile layout at 390px — demo session', () => {
    test.use({ viewport: PHONE });

    async function startDemo(page: Page, persona: 'player' | 'admin') {
        const probe = await page.request.post('/api/v1/demo-signin', { data: { persona } });
        test.skip(!probe.ok(), 'demo data not seeded — run seed_demo.py against the backend');

        // Go through the UI so the SPA adopts the session the way a visitor does.
        await page.goto('/');
        await page.waitForLoadState('networkidle');
        await page.getByTestId(persona === 'player' ? 'cta-tour-club' : 'cta-admin-demo').click();
        await page.waitForURL(persona === 'player' ? '**/player' : '**/admin/season', {
            timeout: 20_000,
        });
        await page.waitForLoadState('networkidle');
    }

    const PLAYER_ROUTES = [
        '/player',
        '/league',   // player home: the "Find a Player" filter grid lives here
        '/player/leagues',
        '/player/tournaments',
        '/matches/history',
        '/stats',
        '/groups',
        '/profile',
    ];

    test('player routes have no horizontal overflow', async ({ page }) => {
        await startDemo(page, 'player');
        for (const path of PLAYER_ROUTES) {
            await page.goto(path);
            await page.waitForLoadState('networkidle');
            await expectNoHorizontalOverflow(page, `player ${path}`);
        }
    });

    test('player bottom nav is on screen and every item fits', async ({ page }) => {
        await startDemo(page, 'player');
        const items = page.locator('.mobile-bottom-nav .mobile-nav-item');
        await expect(items).toHaveCount(5);
        for (let i = 0; i < 5; i++) {
            const box = (await items.nth(i).boundingBox())!;
            expect(box.x + box.width, `bottom nav item ${i} runs off screen`).toBeLessThanOrEqual(
                PHONE.width + 1
            );
        }
    });

    test('every dashboard table sits inside a scroll wrapper', async ({ page }) => {
        await startDemo(page, 'player');
        await page.goto('/player');
        await page.waitForLoadState('networkidle');

        // Asserted as an invariant rather than "a wrapper exists", because which
        // tables render depends on how far the seeded demo league has progressed —
        // standings only appear once a score is in.
        const unwrapped = await page.evaluate(() =>
            Array.from(document.querySelectorAll('table'))
                .filter((t) => !t.closest('.table-scroll'))
                .map((t) => t.className || '(no class)')
        );
        expect(unwrapped, `tables with no .table-scroll ancestor: ${unwrapped.join(', ')}`).toEqual(
            []
        );

        await expectNoHorizontalOverflow(page, 'player dashboard');
    });

    const ADMIN_ROUTES = [
        '/admin/leagues',
        '/admin/tournaments',
        '/admin/season',
        '/admin/create-league',
        '/admin/create-tournament',
        '/profile',
    ];

    test('club routes have no horizontal overflow', async ({ page }) => {
        await startDemo(page, 'admin');
        for (const path of ADMIN_ROUTES) {
            await page.goto(path);
            await page.waitForLoadState('networkidle');
            await expectNoHorizontalOverflow(page, `club ${path}`);
        }
    });

    test('club form grids collapse to one column', async ({ page }) => {
        await startDemo(page, 'admin');
        await page.goto('/admin/create-league');
        await page.waitForLoadState('networkidle');

        // The .grid-3 row (duration / group size / format) was the worst offender:
        // three numeric inputs squeezed into ~110px columns at this width.
        const row = page.locator('.grid-3').first();
        await expect(row).toBeVisible();
        const tops = await row.locator('.form-group').evaluateAll((els) =>
            els.map((el) => Math.round(el.getBoundingClientRect().top))
        );
        expect(new Set(tops).size, 'the .grid-3 fields are still on one row').toBeGreaterThan(1);

        await expectTappable(page, 'button[type="submit"]', 'create league button');
    });

    test('club shell: scrolling tab strip, and no space reserved for a bar it never shows', async ({
        page,
    }) => {
        await startDemo(page, 'admin');

        // Clubs deliberately have no bottom nav — so they must not get its padding
        // either. This guards the fix for the dead 70px that used to apply to
        // every mobile user regardless of whether the bar was rendered.
        await expect(page.locator('.mobile-bottom-nav')).toHaveCount(0);
        const padBottom = await page
            .locator('.main-content')
            .evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom));
        expect(padBottom, 'club pages reserve space for a bar that is not rendered').toBeLessThan(70);

        // The last tab must be reachable by scrolling the strip.
        const strip = page.locator('.header-nav-tabs');
        await strip.evaluate((el) => {
            el.scrollLeft = el.scrollWidth;
        });
        await expect(page.locator('.nav-tab-link').last()).toBeInViewport();
    });
});
