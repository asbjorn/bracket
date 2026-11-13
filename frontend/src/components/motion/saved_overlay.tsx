import { Text } from '@mantine/core';
import { useEffect } from 'react';

import classes from './saved_overlay.module.css';

const SHOWN_MS = 1700;

/**
 * A large confirmation after saving (e.g. a result at the side of the pitch): a check that
 * draws itself and the saved text, gone by itself after a moment. Tapping closes it at once.
 */
export default function SavedOverlay({
  title,
  message,
  onDone,
}: {
  title: string;
  message: string;
  onDone: () => void;
}) {
  useEffect(() => {
    const timer = setTimeout(onDone, SHOWN_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <div className={classes.overlay} onClick={onDone} role="status" aria-live="assertive">
      <div className={classes.box}>
        <div className={classes.circle}>
          <svg className={classes.check} viewBox="0 0 52 52" aria-hidden>
            <path d="M14 27 l8 8 l16 -18" />
          </svg>
        </div>
        <Text fw={800} size="lg">
          {title}
        </Text>
        <Text size="md">{message}</Text>
      </div>
    </div>
  );
}
