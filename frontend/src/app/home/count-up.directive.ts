import { Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

/**
 * Counts the element's number up from 0 when it scrolls into view.
 * The final value is rendered server-side / before JS, so nothing is ever blank.
 */
@Directive({
  selector: '[spCountUp]',
  standalone: true,
})
export class CountUpDirective {
  private el = inject<ElementRef<HTMLElement>>(ElementRef);

  spCountUp = input.required<number>();
  decimals = input(0);
  suffix = input('');
  durationMs = input(1400);

  constructor() {
    afterNextRender(() => {
      const node = this.el.nativeElement;
      const target = this.spCountUp();
      node.textContent = this.format(target);
      if (
        typeof IntersectionObserver === 'undefined' ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ) {
        return;
      }
      const io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          this.animate(node, target);
        }
      });
      io.observe(node);
    });
  }

  private animate(node: HTMLElement, target: number) {
    const start = performance.now();
    const duration = this.durationMs();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      node.textContent = this.format(target * eased);
      if (t < 1) requestAnimationFrame(tick);
      else node.textContent = this.format(target);
    };
    requestAnimationFrame(tick);
  }

  private format(value: number): string {
    const d = this.decimals();
    const num = d > 0 ? value.toFixed(d) : Math.round(value).toLocaleString('en-US');
    return num + this.suffix();
  }
}
