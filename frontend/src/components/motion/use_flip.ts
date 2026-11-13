import { RefObject, useLayoutEffect, useRef } from 'react';

function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

/**
 * Rows that change place slide to their new place instead of jumping (FLIP with the Web
 * Animations API): children of `ref` marked with `data-flip-id` are measured after every render
 * and animated from where they were. Useful when live data reorders a table.
 */
export function useFlip(ref: RefObject<HTMLElement | null>, duration = 650) {
  const positions = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const container = ref.current;
    if (container == null) return;
    const animate = !prefersReducedMotion();
    const next = new Map<string, number>();
    container.querySelectorAll<HTMLElement>('[data-flip-id]').forEach((element) => {
      const id = element.dataset.flipId as string;
      const top = element.offsetTop;
      next.set(id, top);
      const previous = positions.current.get(id);
      if (animate && previous != null && previous !== top && element.animate != null) {
        element.animate(
          [{ transform: `translateY(${previous - top}px)` }, { transform: 'translateY(0)' }],
          { duration, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' },
        );
      }
    });
    positions.current = next;
  });
}
