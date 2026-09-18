import { Directive, ElementRef, afterNextRender, inject } from '@angular/core';

/**
 * Rise/fade-in on scroll. The element is fully visible by default (SSR, no-JS,
 * first paint); only elements still below the fold when JS runs get "armed"
 * and animate in once they intersect. Reduced-motion users never get armed.
 */
@Directive({
  selector: '[spReveal]',
  standalone: true,
  host: { class: 'reveal' },
})
export class RevealDirective {
  private el = inject<ElementRef<HTMLElement>>(ElementRef);

  constructor() {
    afterNextRender(() => {
      const node = this.el.nativeElement;
      if (
        typeof IntersectionObserver === 'undefined' ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ) {
        return;
      }
      if (node.getBoundingClientRect().top >= window.innerHeight) {
        node.classList.add('reveal--armed');
      }
      const io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            node.classList.add('reveal--in');
            io.disconnect();
          }
        },
        { rootMargin: '0px 0px -8% 0px' }
      );
      io.observe(node);
    });
  }
}
