import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach } from 'vitest';
import { BrandLogoComponent } from './brand-logo';

describe('BrandLogoComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [BrandLogoComponent] }).compileComponents();
  });

  it('renders both words on one line as plain, selectable text', () => {
    const fixture = TestBed.createComponent(BrandLogoComponent);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;

    // Tracking is CSS letter-spacing, not literal spaces, so the DOM keeps real words.
    expect(el.querySelector('.brand__top')?.textContent).toBe('Stacked');
    expect(el.querySelector('.brand__bottom')?.textContent).toBe('Paddle');
  });

  it('exposes a single accessible name for the mark', () => {
    const fixture = TestBed.createComponent(BrandLogoComponent);
    fixture.detectChanges();
    const mark = fixture.nativeElement.querySelector('.brand') as HTMLElement;

    expect(mark.getAttribute('role')).toBe('img');
    expect(mark.getAttribute('aria-label')).toBe('StackedPaddle');
    expect(mark.querySelector('.brand__top')?.getAttribute('aria-hidden')).toBe('true');
    expect(mark.querySelector('.brand__bottom')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('allows the accessible name to be overridden', () => {
    const fixture = TestBed.createComponent(BrandLogoComponent);
    fixture.componentRef.setInput('label', 'Join StackedPaddle');
    fixture.detectChanges();

    const mark = fixture.nativeElement.querySelector('.brand') as HTMLElement;
    expect(mark.getAttribute('aria-label')).toBe('Join StackedPaddle');
  });
});
