import { Component, input } from '@angular/core';

/**
 * The StackedPaddle wordmark, on one line: a light, wide-tracked "S T A C K E D"
 * running straight into a bold, compact "PADDLE" with no word gap.
 *
 * Every letter is the same size and sits on one baseline, so the contrast reads
 * purely as weight and tracking. Tracking is real letter-spacing rather than
 * literal spaces, so screen readers and copy/paste still get plain words.
 *
 * Scale it by setting `font-size` on the host; every internal measurement is in
 * `em`. Renders as a single `role="img"` so the mark is announced once. Inside a
 * link or heading that already has its own `aria-label`, that label wins and
 * this one is not announced twice.
 */
@Component({
  selector: 'app-brand-logo',
  standalone: true,
  template: `
    <span class="brand" role="img" [attr.aria-label]="label()">
      <span class="brand__top" aria-hidden="true">Stacked</span>
      <span class="brand__bottom" aria-hidden="true">Paddle</span>
    </span>
  `,
  styles: [
    `
      :host {
        display: inline-block;
        line-height: 1;
      }

      .brand {
        display: inline-flex;
        align-items: baseline;
        font-family: var(--font-body, system-ui, -apple-system, sans-serif);
        color: inherit;
        white-space: nowrap;
        /* Ignore any tracking the host context sets — the lockup defines its own. */
        letter-spacing: normal;
        line-height: 1;
      }

      .brand__top {
        font-size: 1em;
        font-weight: 300;
        text-transform: uppercase;
        letter-spacing: 0.3em;
        /* Tracking also trails the final D. Cancel it exactly so PADDLE butts
           straight onto the D with no word gap. */
        margin-right: -0.3em;
      }

      .brand__bottom {
        font-size: 1em;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: -0.012em;
      }
    `,
  ],
})
export class BrandLogoComponent {
  /** Accessible name for the mark. Override for contexts like "Join StackedPaddle". */
  label = input('StackedPaddle');
}
