import { Component, input } from '@angular/core';

/**
 * The StackedPaddle icon: a lime rounded tile carrying the paddle glyph
 * (an ellipse head over a short handle), in the ink colour that pairs with it.
 *
 * This is the app's single icon mark — the landing nav, the footer, the
 * signed-in header and every auth card render this component, so the icon is
 * identical everywhere and follows the theme toggle through `--ball` /
 * `--ball-ink` rather than any literal colour.
 *
 * Scale it by setting `font-size` on the host; the tile is `1em` square and
 * every internal measurement is in `em`. Decorative by default (`aria-hidden`),
 * because it normally sits beside `<app-brand-logo>`, which already carries the
 * accessible name. Pass `label` when the icon stands alone.
 */
@Component({
  selector: 'app-brand-mark',
  standalone: true,
  template: `
    <span
      class="mark"
      [attr.role]="label() ? 'img' : null"
      [attr.aria-label]="label() || null"
      [attr.aria-hidden]="label() ? null : 'true'"
    >
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
        <ellipse cx="12" cy="9.5" rx="6.5" ry="7.5" fill="currentColor" />
        <rect x="10.4" y="15.5" width="3.2" height="6.5" rx="1.4" fill="currentColor" />
      </svg>
    </span>
  `,
  styles: [
    `
      :host {
        /* 30px tile — the size the nav, footer and signed-in header all use. */
        display: inline-block;
        font-size: 30px;
        line-height: 1;
      }

      .mark {
        display: grid;
        place-items: center;
        width: 1em;
        height: 1em;
        border-radius: 0.3em;
        background: var(--ball);
        color: var(--ball-ink);
        box-shadow: 0 0.133em 0.466em rgba(var(--ball-rgb), 0.3);
      }

      .mark svg {
        display: block;
        width: 0.534em;
        height: 0.534em;
      }
    `,
  ],
})
export class BrandMarkComponent {
  /** Accessible name. Leave empty where a wordmark beside it already names the brand. */
  label = input('');
}
