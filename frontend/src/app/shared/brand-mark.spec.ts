import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach } from 'vitest';
import { BrandMarkComponent } from './brand-mark';

describe('BrandMarkComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [BrandMarkComponent] }).compileComponents();
  });

  it('renders the paddle glyph inside the tile', () => {
    const fixture = TestBed.createComponent(BrandMarkComponent);
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;

    const svg = el.querySelector('.mark svg');
    expect(svg).toBeTruthy();
    // Paddle head over a short handle — the one icon the whole app shares.
    expect(svg!.querySelector('ellipse')).toBeTruthy();
    expect(svg!.querySelector('rect')).toBeTruthy();
  });

  it('is decorative by default, since a wordmark usually names the brand beside it', () => {
    const fixture = TestBed.createComponent(BrandMarkComponent);
    fixture.detectChanges();
    const mark = fixture.nativeElement.querySelector('.mark') as HTMLElement;

    expect(mark.getAttribute('aria-hidden')).toBe('true');
    expect(mark.getAttribute('role')).toBeNull();
    expect(mark.getAttribute('aria-label')).toBeNull();
  });

  it('takes an accessible name when it stands alone', () => {
    const fixture = TestBed.createComponent(BrandMarkComponent);
    fixture.componentRef.setInput('label', 'StackedPaddle');
    fixture.detectChanges();
    const mark = fixture.nativeElement.querySelector('.mark') as HTMLElement;

    expect(mark.getAttribute('role')).toBe('img');
    expect(mark.getAttribute('aria-label')).toBe('StackedPaddle');
    expect(mark.getAttribute('aria-hidden')).toBeNull();
  });
});
