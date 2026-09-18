import { test, expect } from '@playwright/test';

/**
 * Book a demo page (/book-demo).
 * The POST is intercepted with page.route, so no backend is required.
 */
test.describe('Book a demo page', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/book-demo');
        await page.waitForLoadState('networkidle');
    });

    test('renders the marketing copy, agenda and form without the app chrome', async ({ page }) => {
        await expect(page.getByRole('heading', { level: 1 })).toContainText('running in 20 min.');
        await expect(page.locator('.agenda__item')).toHaveCount(4);
        await expect(page.getByTestId('book-demo-form')).toBeVisible();
        await expect(page.getByTestId('demo-nav-back')).toHaveAttribute('href', '/');
        await expect(page.getByTestId('demo-nav-club-signin')).toHaveAttribute('href', '/admin/login');
        // Marketing pages are full-bleed: no signed-in header, no padded main
        await expect(page.locator('header.global-header')).toHaveCount(0);
        await expect(page.locator('main.main-content--landing')).toHaveCount(1);
    });

    test('blocks submit and highlights required fields when empty', async ({ page }) => {
        let posted = false;
        await page.route('**/api/v1/book-demo', route => { posted = true; return route.abort(); });

        await page.getByTestId('book-demo-submit').click();

        await expect(page.locator('.form-summary')).toBeVisible();
        for (const field of ['name', 'email', 'clubName']) {
            await expect(page.locator(`#field-${field}`)).toHaveAttribute('aria-invalid', 'true');
        }
        expect(posted).toBe(false);
    });

    test('submits the request and shows the confirmation', async ({ page }) => {
        let body: any = null;
        await page.route('**/api/v1/book-demo', async route => {
            body = route.request().postDataJSON();
            await route.fulfill({
                status: 201,
                contentType: 'application/json',
                body: JSON.stringify({ request_id: 'abc123', message: "Thanks! We'll be in touch." }),
            });
        });

        await page.fill('#field-name', '  Dana Whitfield ');
        await page.fill('#field-email', 'dana@metropaddle.com');
        await page.fill('#field-clubName', 'Metro Paddle Club');
        await page.selectOption('#field-clubSize', { label: '150–400 players' });
        await page.fill('#field-message', 'Three ladders and a summer bracket.');
        await page.getByTestId('book-demo-submit').click();

        const success = page.getByTestId('book-demo-success');
        await expect(success).toBeVisible();
        await expect(success).toContainText("Thanks! We'll be in touch.");
        await expect(success).toContainText('abc123');
        await expect(page.getByTestId('book-demo-form')).toHaveCount(0);

        expect(body).toEqual({
            name: 'Dana Whitfield',
            email: 'dana@metropaddle.com',
            club_name: 'Metro Paddle Club',
            club_size: '150–400 players',
            message: 'Three ladders and a summer bracket.',
        });
    });

    test('shows a server validation error inline on the mapped field', async ({ page }) => {
        await page.route('**/api/v1/book-demo', route => route.fulfill({
            status: 422,
            contentType: 'application/json',
            body: JSON.stringify({
                detail: [{ loc: ['body', 'club_name'], msg: 'club_name must not be blank', type: 'value_error' }],
            }),
        }));

        await page.fill('#field-name', 'Dana');
        await page.fill('#field-email', 'dana@metropaddle.com');
        await page.fill('#field-clubName', 'MP');
        await page.getByTestId('book-demo-submit').click();

        await expect(page.locator('#field-clubName')).toHaveAttribute('aria-invalid', 'true');
        await expect(page.locator('p#err-clubName')).toContainText(/must not be blank/i);
        await expect(page.getByTestId('book-demo-form')).toBeVisible();
    });

    test('stacks to one column on phones with no horizontal scroll', async ({ page }) => {
        await page.setViewportSize({ width: 400, height: 800 });
        await page.reload();
        await page.waitForLoadState('networkidle');

        await expect(page.getByTestId('book-demo-form')).toBeVisible();
        const overflow = await page.evaluate(
            () => document.documentElement.scrollWidth - document.documentElement.clientWidth
        );
        expect(overflow).toBeLessThanOrEqual(0);
    });
});
