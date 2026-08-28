import { Injectable, signal } from '@angular/core';

export type ConfirmTone = 'danger' | 'primary';

export interface ConfirmOptions {
  /** Bold header — the primary question, e.g. "Delete Sora Tournament?" */
  title: string;
  /** Regular text — spell out exactly what is lost and whether it is permanent. */
  message: string;
  /** Action-oriented label for the confirm button, e.g. "Delete League". */
  confirmLabel?: string;
  /** Action-oriented label for the dismiss button, e.g. "Keep League". */
  cancelLabel?: string;
  /** 'danger' (default) styles the confirm button red; 'primary' uses the brand accent. */
  tone?: ConfirmTone;
}

interface ConfirmState extends Required<ConfirmOptions> {
  resolve: (confirmed: boolean) => void;
}

/**
 * App-wide replacement for the browser `confirm()` dialog. Renders through the
 * single <app-confirm-host> in the app shell. Call `ask()` and await the result:
 *
 *   if (!(await this.confirm.ask({ title: '…', message: '…' }))) return;
 */
@Injectable({ providedIn: 'root' })
export class ConfirmService {
  readonly state = signal<ConfirmState | null>(null);

  ask(options: ConfirmOptions): Promise<boolean> {
    // If a dialog is somehow already open, treat it as cancelled.
    this.state()?.resolve(false);

    return new Promise<boolean>((resolve) => {
      this.state.set({
        confirmLabel: 'Confirm',
        cancelLabel: 'Cancel',
        tone: 'danger',
        ...options,
        resolve,
      });
    });
  }

  respond(confirmed: boolean): void {
    const current = this.state();
    if (!current) return;
    this.state.set(null);
    current.resolve(confirmed);
  }
}
