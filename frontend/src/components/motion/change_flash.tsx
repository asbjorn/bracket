import { ReactNode, useEffect, useRef, useState } from 'react';

import classes from '@components/dashboard/public.module.css';

/**
 * Shows its children and flashes briefly when `value` changes (not on the first render), e.g. a
 * score or the points of a team that just changed on a live page.
 */
export function ChangeFlash({ value, children }: { value: unknown; children: ReactNode }) {
  const previous = useRef(value);
  const [changes, setChanges] = useState(0);
  useEffect(() => {
    if (previous.current !== value) {
      previous.current = value;
      setChanges((count) => count + 1);
    }
  }, [value]);
  return (
    <span
      key={changes}
      className={changes > 0 ? classes.changed : undefined}
      style={{ display: 'inline-block', borderRadius: 'inherit' }}
    >
      {children}
    </span>
  );
}
