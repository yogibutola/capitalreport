import { Component, inject } from '@angular/core';
import { ToastService } from './toast.service';

@Component({
  selector: 'app-toast-host',
  standalone: true,
  template: `
    <div class="toast-host" role="region" aria-label="Notifications">
      @for (toast of toasts(); track toast.id) {
        <div
          class="toast"
          [class.toast--success]="toast.kind === 'success'"
          [class.toast--error]="toast.kind === 'error'"
          [attr.role]="toast.kind === 'error' ? 'alert' : 'status'"
          [attr.aria-live]="toast.kind === 'error' ? 'assertive' : 'polite'"
        >
          @if (toast.kind === 'error') {
            <svg class="toast__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          } @else {
            <svg class="toast__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          }
          <span class="toast__body">{{ toast.text }}</span>
          <button type="button" class="toast__close" aria-label="Dismiss" (click)="toastService.dismiss(toast.id)">
            &times;
          </button>
        </div>
      }
    </div>
  `,
})
export class ToastHostComponent {
  protected toastService = inject(ToastService);
  protected toasts = this.toastService.toasts;
}
