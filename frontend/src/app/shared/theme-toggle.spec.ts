import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ThemeToggleComponent } from './theme-toggle';
import { ThemeService } from '../theme.service';

describe('ThemeToggleComponent', () => {
  beforeEach(async () => {
    localStorage.clear();
    // Pin the OS preference so the control always starts from dark.
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({ matches: false, media: query }))
    );
    await TestBed.configureTestingModule({ imports: [ThemeToggleComponent] }).compileComponents();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  function render() {
    const fixture = TestBed.createComponent(ThemeToggleComponent);
    fixture.detectChanges();
    return {
      fixture,
      button: fixture.nativeElement.querySelector('button') as HTMLButtonElement,
      theme: TestBed.inject(ThemeService),
    };
  }

  it('announces the current theme as a switch, not just an action', () => {
    const { button } = render();

    expect(button.getAttribute('role')).toBe('switch');
    expect(button.getAttribute('aria-checked')).toBe('false');
    expect(button.getAttribute('aria-label')).toBe('Switch to light theme');
  });

  it('flips the theme when clicked', () => {
    const { fixture, button, theme } = render();

    button.click();
    fixture.detectChanges();

    expect(theme.theme()).toBe('light');
    expect(button.getAttribute('aria-checked')).toBe('true');
    expect(button.getAttribute('aria-label')).toBe('Switch to dark theme');
  });

  it('marks the host so the moon icon takes over in light mode', () => {
    const { fixture, button } = render();
    const host: HTMLElement = fixture.nativeElement;

    expect(host.classList.contains('is-light')).toBe(false);

    button.click();
    fixture.detectChanges();

    expect(host.classList.contains('is-light')).toBe(true);
  });

  it('keeps both icons mounted so the control does not resize on toggle', () => {
    const { fixture } = render();
    const el: HTMLElement = fixture.nativeElement;

    expect(el.querySelector('.theme-toggle__icon--sun')).not.toBeNull();
    expect(el.querySelector('.theme-toggle__icon--moon')).not.toBeNull();
  });
});
