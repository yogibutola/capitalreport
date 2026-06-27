import { Injectable, signal, PLATFORM_ID, inject, effect } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type Theme = 'dark' | 'light';

@Injectable({
    providedIn: 'root'
})
export class ThemeService {
    private platformId = inject(PLATFORM_ID);

    // Default theme is light
    theme = signal<Theme>('light');

    constructor() {
        if (isPlatformBrowser(this.platformId)) {
            const storedTheme = localStorage.getItem('app_theme') as Theme;
            if (storedTheme) {
                this.theme.set(storedTheme);
            }
        }

        // Persist theme changes
        effect(() => {
            if (isPlatformBrowser(this.platformId)) {
                localStorage.setItem('app_theme', this.theme());
            }
        });
    }

    toggleTheme() {
        this.theme.update(current => current === 'dark' ? 'light' : 'dark');
    }

    setTheme(theme: Theme) {
        this.theme.set(theme);
    }
}
