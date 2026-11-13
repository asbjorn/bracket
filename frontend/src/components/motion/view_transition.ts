import { flushSync } from 'react-dom';

/**
 * Runs a React state update inside a View Transition, so the browser animates between the old
 * and the new page (elements with the same `view-transition-name` move to their new place).
 * Browsers without View Transitions, and people who prefer reduced motion, just get the update.
 */
export function withViewTransition(update: () => void) {
  const reduced =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  if (reduced || typeof document === 'undefined' || !('startViewTransition' in document)) {
    update();
    return;
  }
  document.startViewTransition(() => {
    flushSync(update);
  });
}
