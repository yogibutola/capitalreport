import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { PLATFORM_ID } from '@angular/core';
import { ThemeService, THEME_STORAGE_KEY } from './theme.service';

/** Install a `matchMedia` stub that reports the given OS preference. */
function stubPrefersLight(prefersLight: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query.includes('light') ? prefersLight : !prefersLight,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
  );
}

function makeService() {
  return TestBed.configureTestingModule({ providers: [ThemeService] }).inject(ThemeService);
}

describe('ThemeService', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.resetTestingModule();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('defaults to dark when nothing is stored and the OS prefers dark', () => {
    stubPrefersLight(false);
    expect(makeService().theme()).toBe('dark');
  });

  it('follows the OS preference when the user has never chosen', () => {
    stubPrefersLight(true);
    expect(makeService().theme()).toBe('light');
  });

  it('prefers a stored choice over the OS preference', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    stubPrefersLight(true);

    expect(makeService().theme()).toBe('dark');
  });

  it('ignores a corrupt stored value and falls back', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'chartreuse');
    stubPrefersLight(false);

    expect(makeService().theme()).toBe('dark');
  });

  it('toggles between the two themes', () => {
    stubPrefersLight(false);
    const service = makeService();

    service.toggleTheme();
    expect(service.theme()).toBe('light');

    service.toggleTheme();
    expect(service.theme()).toBe('dark');
  });

  it('persists the chosen theme so it survives a reload', () => {
    stubPrefersLight(false);
    makeService().toggleTheme();

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
    // A fresh instance, as after a reload, picks the stored choice back up.
    TestBed.resetTestingModule();
    expect(makeService().theme()).toBe('light');
  });

  it('still applies the theme for the session when storage throws', () => {
    stubPrefersLight(false);
    const service = makeService();
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => service.setTheme('light')).not.toThrow();
    expect(service.theme()).toBe('light');
    vi.restoreAllMocks();
  });

  it('resolves to dark on the server, where there is no storage or media query', () => {
    const service = TestBed.configureTestingModule({
      providers: [ThemeService, { provide: PLATFORM_ID, useValue: 'server' }],
    }).inject(ThemeService);

    expect(service.theme()).toBe('dark');
  });
});
