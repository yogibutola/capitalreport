import { Component, HostListener, inject } from '@angular/core';
import { ConfirmService } from './confirm.service';

@Component({
  selector: 'app-confirm-host',
  standalone: true,
  template: `
    @if (confirm.state(); as dialog) {
      <div class="confirm-backdrop" (click)="confirm.respond(false)">
        <div
          class="confirm-dialog"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          aria-describedby="confirm-message"
          (click)="$event.stopPropagation()"
        >
          <div
            class="confirm-dialog__icon"
            [class.confirm-dialog__icon--primary]="dialog.tone === 'primary'"
            aria-hidden="true"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>

          <h2 class="confirm-dialog__title" id="confirm-title">{{ dialog.title }}</h2>
          <p class="confirm-dialog__message" id="confirm-message">{{ dialog.message }}</p>

          <div class="confirm-dialog__actions">
            <button
              type="button"
              class="confirm-dialog__btn confirm-dialog__btn--cancel"
              (click)="confirm.respond(false)"
              autofocus
            >
              {{ dialog.cancelLabel }}
            </button>
            <button
              type="button"
              class="confirm-dialog__btn"
              [class.confirm-dialog__btn--danger]="dialog.tone === 'danger'"
              [class.confirm-dialog__btn--primary]="dialog.tone === 'primary'"
              (click)="confirm.respond(true)"
            >
              {{ dialog.confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    }
  `,
})
export class ConfirmHostComponent {
  protected confirm = inject(ConfirmService);

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.confirm.respond(false);
  }
}
