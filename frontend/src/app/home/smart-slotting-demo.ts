import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';

interface DemoPlayer {
  name: string;
  dupr: number;
}

interface Pairing {
  a: DemoPlayer;
  b: DemoPlayer;
}

export const BALANCE_TOLERANCE = 0.15;

const PLAYER_POOL: DemoPlayer[] = [
  { name: 'Maya', dupr: 4.1 },
  { name: 'Jordan', dupr: 4.0 },
  { name: 'Priya', dupr: 4.3 },
  { name: 'Leo', dupr: 4.2 },
  { name: 'Sam', dupr: 3.8 },
  { name: 'Aisha', dupr: 3.7 },
  { name: 'Diego', dupr: 4.5 },
  { name: 'Noor', dupr: 4.4 },
  { name: 'Ben', dupr: 3.6 },
  { name: 'Chloe', dupr: 3.9 },
  { name: 'Rafael', dupr: 4.6 },
  { name: 'Ines', dupr: 4.1 },
  { name: 'Tomas', dupr: 3.9 },
  { name: 'Kenji', dupr: 4.3 },
  { name: 'Zara', dupr: 3.5 },
  { name: 'Owen', dupr: 4.0 },
  { name: 'Lucia', dupr: 4.2 },
  { name: 'Amir', dupr: 3.7 },
];

const TIMES = ['6:00', '6:40', '7:20'];
const COURTS = ['Court 1', 'Court 2', 'Court 3'];

// Deterministic first layout so server and client render identical markup.
const INITIAL_ORDER = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17];

@Component({
  selector: 'app-smart-slotting-demo',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="sched" [class.sched--shuffling]="shuffling()">
      <div class="sched__head">
        <div>
          <div class="sched__title">Tuesday night · Open play</div>
          <div class="sched__sub mono" data-testid="slotting-status">
            {{ playerCount }} players · 0 conflicts · balanced ±{{ tolerance }}
          </div>
        </div>
        <button
          type="button"
          class="sched__reslot"
          (click)="reslot()"
          data-testid="reslot-button"
          aria-label="Re-slot all courts"
        >
          <span aria-hidden="true">↻</span> Re-slot
        </button>
      </div>

      <div class="sched__grid" role="table" aria-label="Court schedule">
        <div class="sched__row sched__row--head" role="row">
          <div class="sched__time mono" role="columnheader">Time</div>
          @for (court of courts; track court) {
            <div class="sched__court mono" role="columnheader">{{ court }}</div>
          }
        </div>
        @for (row of rows(); track row.time) {
          <div class="sched__row" role="row">
            <div class="sched__time mono" role="rowheader">{{ row.time }}</div>
            @for (p of row.pairings; track $index) {
              <div
                class="sched__cell"
                [class.sched__cell--balanced]="isBalanced(p)"
                role="cell"
                data-testid="slot-cell"
              >
                <div class="sched__names">{{ p.a.name }} · {{ p.b.name }}</div>
                <div class="sched__dupr mono">
                  {{ p.a.dupr.toFixed(1) }} vs {{ p.b.dupr.toFixed(1) }}
                </div>
              </div>
            }
          </div>
        }
      </div>

      <div class="sched__legend mono" aria-live="polite">
        <span class="sched__dot" aria-hidden="true"></span>
        balanced ±{{ tolerance }} · {{ balancedCount() }} of {{ cellCount }} courts
      </div>
    </div>
  `,
  styles: `
    :host { display: block; }
    .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
    .sched {
      background: var(--surface-2);
      border-radius: var(--radius-card);
      padding: 18px;
      box-shadow:
        0 1px 0 rgba(255, 255, 255, 0.03) inset,
        0 18px 50px rgba(0, 0, 0, 0.45),
        0 4px 14px rgba(0, 0, 0, 0.3);
    }
    .sched__head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    .sched__title { font-weight: 700; color: var(--text); font-size: 0.95rem; }
    .sched__sub { color: var(--muted); font-size: 0.72rem; margin-top: 4px; letter-spacing: 0.02em; }
    .sched__reslot {
      flex-shrink: 0;
      font: 600 0.8rem var(--font-body);
      color: var(--ball-ink);
      background: var(--ball);
      border: 0;
      border-radius: var(--radius-pill);
      padding: 8px 14px;
      cursor: pointer;
      box-shadow: 0 6px 18px rgba(205, 240, 58, 0.28);
      transition: transform var(--ease-lift), box-shadow var(--ease-lift);
    }
    .sched__reslot:hover { transform: var(--lift); box-shadow: 0 10px 24px rgba(205, 240, 58, 0.36); }
    .sched__reslot:focus-visible { outline: 2px solid var(--text); outline-offset: 3px; }
    .sched__grid { display: grid; gap: 6px; }
    .sched__row { display: grid; grid-template-columns: 52px repeat(3, minmax(0, 1fr)); gap: 6px; }
    .sched__row--head { margin-bottom: 2px; }
    .sched__time, .sched__court {
      font-size: 0.66rem;
      color: var(--muted-2);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      align-self: center;
    }
    .sched__court { padding-left: 10px; }
    .sched__time { color: var(--muted); }
    .sched__cell {
      background: var(--surface);
      border: 1px solid var(--line-soft);
      border-radius: 10px;
      padding: 9px 10px;
      min-width: 0;
      transition: opacity 220ms ease, border-color 220ms ease, background-color 220ms ease, transform 220ms ease;
    }
    .sched__cell--balanced {
      border-color: rgba(205, 240, 58, 0.55);
      background: rgba(205, 240, 58, 0.06);
    }
    .sched__cell--balanced .sched__dupr { color: var(--ball); }
    .sched__names {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .sched__dupr { font-size: 0.68rem; color: var(--muted); margin-top: 3px; }
    .sched--shuffling .sched__cell { opacity: 0.35; transform: translateY(3px); }
    .sched__legend {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 14px;
      font-size: 0.66rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }
    .sched__dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--ball);
      box-shadow: 0 0 10px rgba(205, 240, 58, 0.6);
    }
    @media (max-width: 480px) {
      .sched { padding: 14px; }
      .sched__row { grid-template-columns: 40px repeat(3, minmax(0, 1fr)); gap: 4px; }
      .sched__cell { padding: 7px 6px; }
      .sched__names { font-size: 0.68rem; }
      .sched__dupr { font-size: 0.6rem; }
      .sched__court { padding-left: 6px; letter-spacing: 0.06em; }
    }
    @media (prefers-reduced-motion: reduce) {
      .sched__cell, .sched__reslot { transition: none; }
      .sched--shuffling .sched__cell { opacity: 1; transform: none; }
    }
  `,
})
export class SmartSlottingDemoComponent {
  readonly courts = COURTS;
  readonly tolerance = BALANCE_TOLERANCE.toFixed(2);
  readonly playerCount = PLAYER_POOL.length;
  readonly cellCount = TIMES.length * COURTS.length;

  private order = signal<number[]>(INITIAL_ORDER);
  shuffling = signal(false);

  rows = computed(() => {
    const players = this.order().map((i) => PLAYER_POOL[i]);
    return TIMES.map((time, r) => ({
      time,
      pairings: COURTS.map((_, c): Pairing => {
        const idx = (r * COURTS.length + c) * 2;
        return { a: players[idx], b: players[idx + 1] };
      }),
    }));
  });

  balancedCount = computed(() =>
    this.rows().reduce((n, row) => n + row.pairings.filter((p) => this.isBalanced(p)).length, 0)
  );

  isBalanced(p: Pairing): boolean {
    return Math.abs(p.a.dupr - p.b.dupr) <= BALANCE_TOLERANCE + 1e-9;
  }

  reslot() {
    // Shuffle, then sort by DUPR with jitter so most (not all) matchups land balanced.
    const shuffled = [...PLAYER_POOL.keys()].sort(() => Math.random() - 0.5);
    const jittered = shuffled
      .map((i) => ({ i, key: PLAYER_POOL[i].dupr + (Math.random() - 0.5) * 0.4 }))
      .sort((x, y) => x.key - y.key)
      .map((x) => x.i);
    this.shuffling.set(true);
    this.order.set(jittered);
    setTimeout(() => this.shuffling.set(false), 220);
  }
}
