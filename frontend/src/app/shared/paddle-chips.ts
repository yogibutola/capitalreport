import { Component, computed, input } from '@angular/core';
import { Paddle } from './paddle';

/**
 * Renders a player's paddles as read-only chips.
 *
 * Shared rather than per-component CSS because four screens show these — the
 * profile, the Find-a-Player card, and both rosters — and Angular's emulated
 * encapsulation means a stylesheet can't be shared without going global. (See
 * `.pill` in home.css for the alternative: a chip scoped to one component and
 * therefore unreusable.)
 *
 * Renders nothing when the list is empty, so every caller gets the empty case
 * for free. `max` truncates for dense roster rows; the remainder is summarised
 * as "+N" rather than dropped silently.
 *
 * The tint is neutral, not `--ball-rgb`: on a search card the DUPR badge should
 * stay the dominant signal.
 */
@Component({
  selector: 'app-paddle-chips',
  standalone: true,
  template: `
    @if (shown().length) {
      <span class="paddle-chips">
        @for (p of shown(); track $index) {
          <span class="paddle-chip" [title]="label(p)">
            <span class="paddle-chip__brand">{{ p.brand }}</span>
            @if (p.model) {
              <span class="paddle-chip__model">{{ p.model }}</span>
            }
          </span>
        }
        @if (hiddenCount()) {
          <span class="paddle-chip paddle-chip--more" [title]="hiddenLabel()"
            >+{{ hiddenCount() }}</span
          >
        }
      </span>
    }
  `,
  styles: [
    `
      .paddle-chips {
        display: inline-flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
      }

      .paddle-chip {
        display: inline-flex;
        align-items: baseline;
        gap: 5px;
        max-width: 100%;
        padding: 3px 10px;
        border-radius: var(--radius-pill);
        border: 1px solid rgba(var(--tint-rgb), 0.12);
        background: rgba(var(--tint-rgb), 0.06);
        color: var(--text);
        font-family: var(--font-body);
        font-size: 0.72rem;
        line-height: 1.5;
        white-space: nowrap;
        overflow: hidden;
      }

      .paddle-chip__brand {
        font-weight: 600;
      }

      .paddle-chip__model {
        color: var(--muted);
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .paddle-chip--more {
        color: var(--muted);
      }
    `,
  ],
})
export class PaddleChipsComponent {
  paddles = input<Paddle[] | null | undefined>([]);
  /** Show at most this many chips; the rest collapse into a "+N". */
  max = input<number | null>(null);

  private all = computed(() => this.paddles() ?? []);

  shown = computed(() => {
    const limit = this.max();
    const all = this.all();
    return limit != null && limit > 0 ? all.slice(0, limit) : all;
  });

  hiddenCount = computed(() => this.all().length - this.shown().length);

  label(p: Paddle): string {
    return p.model ? `${p.brand} ${p.model}` : p.brand;
  }

  hiddenLabel(): string {
    return this.all()
      .slice(this.shown().length)
      .map((p) => this.label(p))
      .join(', ');
  }
}
