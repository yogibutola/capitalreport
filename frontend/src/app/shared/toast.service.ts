import { Injectable, signal, inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type ToastKind = 'error' | 'success';

export interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
}

/**
 * Global, non-field-specific feedback: connection drops, server failures,
 * expired sessions, and "saved" confirmations. Field-level validation errors
 * belong inline on the form, not here.
 */
@Injectable({ providedIn: 'root' })
export class ToastService {
  private platformId = inject(PLATFORM_ID);
  private nextId = 1;
  private timers = new Map<number, ReturnType<typeof setTimeout>>();

  readonly toasts = signal<Toast[]>([]);

  error(text: string, timeoutMs = 8000): void {
    this.show('error', text, timeoutMs);
  }

  success(text: string, timeoutMs = 4000): void {
    this.show('success', text, timeoutMs);
  }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
    const timer = this.timers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(id);
    }
  }

  private show(kind: ToastKind, text: string, timeoutMs: number): void {
    const id = this.nextId++;
    // Collapse duplicate messages so a flaky connection doesn't stack toasts.
    this.toasts.update((list) => [
      ...list.filter((t) => t.text !== text),
      { id, kind, text },
    ]);

    if (isPlatformBrowser(this.platformId) && timeoutMs > 0) {
      this.timers.set(
        id,
        setTimeout(() => this.dismiss(id), timeoutMs),
      );
    }
  }
}
