import { Injectable, signal } from '@angular/core';

export type Theme = 'dark' | 'light';

/**
 * The app ships a single committed dark theme. The signal is kept so the
 * `data-theme` attribute and any callers keep working, but it is always 'dark'.
 */
@Injectable({
    providedIn: 'root'
})
export class ThemeService {
    theme = signal<Theme>('dark');

    toggleTheme() {
        this.theme.set('dark');
    }

    setTheme(_theme: Theme) {
        this.theme.set('dark');
    }
}
