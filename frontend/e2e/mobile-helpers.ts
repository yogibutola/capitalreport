import { expect, Page } from '@playwright/test';

/**
 * Shared assertions for the phone-width checks.
 *
 * These live outside a .spec file on purpose: Playwright refuses to let one test
 * file import another, and both mobile-responsive.spec.ts and
 * platform-console.spec.ts need them.
 */

/** iPhone 14/15 logical viewport — the width this work targets. */
export const PHONE = { width: 390, height: 844 };

/**
 * Every element whose box pokes past the viewport, ignoring anything inside a
 * scroll or clip container. Descendants of `.table-scroll`, of the header tab
 * strip and of the tournament bracket are *meant* to be wider than the screen —
 * they scroll internally and never widen the page, so flagging them would make
 * these assertions fail on correct code.
 */
async function findOverflowingElements(page: Page): Promise<string[]> {
    return page.evaluate(() => {
        const limit = document.documentElement.clientWidth;
        const offenders: string[] = [];

        const insideScroller = (el: Element): boolean => {
            let p = el.parentElement;
            while (p && p !== document.documentElement) {
                if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX)) return true;
                p = p.parentElement;
            }
            return false;
        };

        for (const el of Array.from(document.body.querySelectorAll('*'))) {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            if (cs.position === 'fixed') continue; // off-canvas menus sit outside on purpose
            const r = el.getBoundingClientRect();
            if (!r.width || !r.height) continue;
            if (r.right <= limit + 1 && r.left >= -1) continue;
            if (insideScroller(el)) continue;

            const cls =
                typeof el.className === 'string' && el.className.trim()
                    ? '.' + el.className.trim().split(/\s+/).join('.')
                    : '';
            offenders.push(
                `${el.tagName.toLowerCase()}${cls} → left=${Math.round(r.left)} right=${Math.round(r.right)} (limit ${limit})`
            );
        }
        return offenders.slice(0, 10); // enough to debug, not a wall of text
    });
}

/**
 * The core assertion: this page fits in the phone.
 *
 * Two checks, because neither is sufficient alone — the landing page sets
 * `overflow-x: clip`, which makes `scrollWidth` lie, while the element sweep
 * alone can't tell a genuinely broken page from one that merely scrolls a table.
 */
export async function expectNoHorizontalOverflow(page: Page, label: string) {
    // Named elements first: when a page is broken this says *what* is too wide,
    // where the document-level number alone only says that something is.
    const offenders = await findOverflowingElements(page);
    expect(
        offenders,
        `${label}: elements wider than the viewport:\n  ${offenders.join('\n  ')}`
    ).toEqual([]);

    const docOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(docOverflow, `${label}: document scrolls sideways by ${docOverflow}px`).toBeLessThanOrEqual(1);
}

/** A control that is on screen and actually hittable. */
export async function expectTappable(page: Page, selector: string, label: string) {
    const el = page.locator(selector).first();
    await expect(el, `${label} is not visible at ${PHONE.width}px`).toBeVisible();

    const box = await el.boundingBox();
    expect(box, `${label} has no layout box`).not.toBeNull();
    expect(box!.x, `${label} starts off the left edge`).toBeGreaterThanOrEqual(-1);
    expect(box!.x + box!.width, `${label} extends past the right edge`).toBeLessThanOrEqual(
        PHONE.width + 1
    );
}

/** True when two elements are stacked vertically rather than sitting side by side. */
export async function expectStacked(
    page: Page,
    topSel: string,
    bottomSel: string,
    label: string
) {
    const a = await page.locator(topSel).first().boundingBox();
    const b = await page.locator(bottomSel).first().boundingBox();
    expect(a, `${label}: ${topSel} not found`).not.toBeNull();
    expect(b, `${label}: ${bottomSel} not found`).not.toBeNull();
    expect(b!.y, `${label}: fields are still side by side at ${PHONE.width}px`).toBeGreaterThan(
        a!.y + a!.height - 2
    );
}
