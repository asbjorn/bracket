import { Progress, ProgressProps } from '@mantine/core';
import { useEffect, useState } from 'react';

/** A progress bar that fills up from empty when shown, and moves smoothly when it changes. */
export default function AnimatedProgress({ value, ...props }: ProgressProps) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setShown(value));
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <Progress value={shown} transitionDuration={900} {...props} />;
}
