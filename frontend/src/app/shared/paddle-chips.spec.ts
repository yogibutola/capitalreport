import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach } from 'vitest';
import { PaddleChipsComponent } from './paddle-chips';

describe('PaddleChipsComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [PaddleChipsComponent] }).compileComponents();
  });

  function render(paddles: unknown, max?: number) {
    const fixture = TestBed.createComponent(PaddleChipsComponent);
    fixture.componentRef.setInput('paddles', paddles);
    if (max !== undefined) fixture.componentRef.setInput('max', max);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('renders nothing at all when there are no paddles', () => {
    expect(render([]).querySelector('.paddle-chips')).toBeNull();
  });

  it('tolerates a null list', () => {
    expect(render(null).querySelector('.paddle-chips')).toBeNull();
  });

  it('renders brand and model as separate spans', () => {
    const el = render([{ brand: 'Joola', model: 'Perseus' }]);
    expect(el.querySelector('.paddle-chip__brand')?.textContent).toBe('Joola');
    expect(el.querySelector('.paddle-chip__model')?.textContent).toBe('Perseus');
  });

  it('omits the model span when there is no model', () => {
    const el = render([{ brand: 'CRBN', model: null }]);
    expect(el.querySelector('.paddle-chip__brand')?.textContent).toBe('CRBN');
    expect(el.querySelector('.paddle-chip__model')).toBeNull();
  });

  it('titles each chip with its full text, for truncated rows', () => {
    const el = render([{ brand: 'Joola', model: 'Perseus' }, { brand: 'CRBN' }]);
    const titles = [...el.querySelectorAll('.paddle-chip')].map((c) => c.getAttribute('title'));
    expect(titles).toEqual(['Joola Perseus', 'CRBN']);
  });

  it('collapses the overflow into a +N rather than dropping it', () => {
    const el = render(
      [{ brand: 'Joola' }, { brand: 'Selkirk' }, { brand: 'CRBN' }],
      1
    );
    expect(el.querySelectorAll('.paddle-chip:not(.paddle-chip--more)')).toHaveLength(1);
    const more = el.querySelector('.paddle-chip--more');
    expect(more?.textContent?.trim()).toBe('+2');
    expect(more?.getAttribute('title')).toBe('Selkirk, CRBN');
  });

  it('shows everything when max is not set', () => {
    const el = render([{ brand: 'Joola' }, { brand: 'Selkirk' }]);
    expect(el.querySelectorAll('.paddle-chip')).toHaveLength(2);
    expect(el.querySelector('.paddle-chip--more')).toBeNull();
  });
});
