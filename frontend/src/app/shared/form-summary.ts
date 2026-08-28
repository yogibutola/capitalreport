import { Component, ElementRef, inject, input, PLATFORM_ID, viewChild } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { NgForm } from '@angular/forms';

interface SummaryItem {
  name: string;
  label: string;
}

/**
 * "Please fix these" box shown at the top of a form after a failed submit.
 * Each row links to its field: the input must carry `id="field-<controlName>"`
 * (e.g. control `name="startDate"` -> `id="field-startDate"`).
 *
 * Usage:
 *   <form #f="ngForm" (ngSubmit)="onSubmit(f)">
 *     <app-form-summary [form]="f" [attempted]="submitAttempted"
 *                       [labels]="{ name: 'League name', startDate: 'Start date' }" />
 */
@Component({
  selector: 'app-form-summary',
  standalone: true,
  template: `
    @if (items.length) {
      <div class="form-summary" role="alert" aria-live="assertive" tabindex="-1" #box>
        <p class="form-summary__title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {{ title() }}
        </p>
        <ul class="form-summary__list">
          @for (item of items; track item.name) {
            <li>
              <button type="button" class="form-summary__link" (click)="focusField(item.name)">
                {{ item.label }}
              </button>
            </li>
          }
        </ul>
      </div>
    }
  `,
})
export class FormSummaryComponent {
  private platformId = inject(PLATFORM_ID);

  form = input.required<NgForm>();
  attempted = input<boolean>(false);
  labels = input<Record<string, string>>({});
  title = input<string>('Please fix the following before continuing:');

  private box = viewChild<ElementRef<HTMLDivElement>>('box');

  get items(): SummaryItem[] {
    if (!this.attempted()) return [];
    const controls = this.form()?.form?.controls ?? {};
    const labels = this.labels();
    return Object.keys(controls)
      .filter((name) => controls[name]?.invalid)
      .map((name) => ({ name, label: labels[name] ?? this.prettify(name) }));
  }

  /** Move focus to the summary box; call after a failed submit. */
  focusSelf(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    queueMicrotask(() => this.box()?.nativeElement?.focus());
  }

  focusField(name: string): void {
    if (!isPlatformBrowser(this.platformId)) return;
    const el = document.getElementById(`field-${name}`);
    if (el) {
      el.focus();
      el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  private prettify(name: string): string {
    const spaced = name.replace(/([A-Z])/g, ' $1').replace(/[_-]/g, ' ').trim();
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
  }
}
