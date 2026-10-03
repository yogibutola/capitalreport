import { Injectable, signal } from '@angular/core';

export type ConfirmTone = 'danger' | 'primary' | 'success';

export interface ConfirmOptions {
  /** Bold header — the primary question, e.g. "Delete Sora Tournament?" */
  title: string;
  /** Regular text — spell out exactly what is lost and whether it is permanent. */
  message: string;
  /** Action-oriented label for the confirm button, e.g. "Delete League". */
  confirmLabel?: string;
  /** Action-oriented label for the dismiss button, e.g. "Keep League". */
  cancelLabel?: string;
  /** 'danger' (default) styles the confirm button red; 'primary' uses the brand accent;
   *  'success' uses the positive green. */
  tone?: ConfirmTone;
}

export interface NoticeOptions {
  /** Bold header, e.g. "You're registered!" */
  title: string;
  /** Regular text — usually the server's response message. */
  message: string;
  /** Label for the single dismiss button. Defaults to "OK". */
  okLabel?: string;
  /** 'success' (default) for a good outcome, 'danger' for a failure. */
  tone?: ConfirmTone;
}

/** 'confirm' asks a question (two buttons); 'notice' reports an outcome (one button). */
export type ConfirmMode = 'confirm' | 'notice';

interface ConfirmState extends Required<ConfirmOptions> {
  mode: ConfirmMode;
  resolve: (confirmed: boolean) => void;
}

/**
 * App-wide replacement for the browser `confirm()` dialog. Renders through the
 * single <app-confirm-host> in the app shell. Call `ask()` and await the result:
 *
 *   if (!(await this.confirm.ask({ title: '…', message: '…' }))) return;
 *
 * `notify()` uses the same dialog with a single button to report an outcome
 * (e.g. a registration response) that the user must acknowledge.
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
        mode: 'confirm',
        resolve,
      });
    });
  }

  notify(options: NoticeOptions): Promise<void> {
    this.state()?.resolve(false);

    return new Promise<void>((resolve) => {
      this.state.set({
        title: options.title,
        message: options.message,
        confirmLabel: options.okLabel ?? 'OK',
        cancelLabel: '',
        tone: options.tone ?? 'success',
        mode: 'notice',
        resolve: () => resolve(),
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
