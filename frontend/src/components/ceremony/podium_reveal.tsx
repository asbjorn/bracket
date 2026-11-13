import { Button, Group, Modal, Text } from '@mantine/core';
import { IconMaximize } from '@tabler/icons-react';
import { CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Podium } from '@openapi';
import classes from './podium_reveal.module.css';

const CONFETTI_COLORS = ['#ffd43b', '#ff6b6b', '#4dabf7', '#69db7c', '#da77f2', '#ffa94d'];
// Shown left to right; revealed 3rd, 2nd, 1st
const COLUMNS = [2, 1, 3];
const REVEAL_ORDER = [3, 2, 1];

function Confetti() {
  // Fixed per mount, so the pieces don't jump on re-render
  const pieces = useMemo(
    () =>
      Array.from({ length: 120 }, (_, index) => ({
        x: `${Math.random() * 100}%`,
        drift: `${(Math.random() - 0.5) * 30}vw`,
        spin: `${Math.round((Math.random() - 0.5) * 1440)}deg`,
        delay: `${Math.random() * 0.8}s`,
        duration: `${2.6 + Math.random() * 2}s`,
        color: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
      })),
    [],
  );
  return (
    <div className={classes.confetti} aria-hidden>
      {pieces.map((piece, index) => (
        <span
          key={index}
          className={classes.piece}
          style={
            {
              '--x': piece.x,
              '--drift': piece.drift,
              '--spin': piece.spin,
              '--delay': piece.delay,
              '--duration': piece.duration,
              '--color': piece.color,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}

/**
 * The podium of a class on a big screen: 3rd, 2nd and 1st place are revealed one by one with a
 * click, Space or the arrow key, and the winner gets confetti. Mount it only while open.
 */
export default function PodiumReveal({
  className,
  podium,
  onClose,
}: {
  className: string;
  podium: Podium;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const stageRef = useRef<HTMLDivElement>(null);
  // How many places are shown: 0 = none, 3 = all
  const [shown, setShown] = useState(0);
  const places = REVEAL_ORDER.filter((place) =>
    podium.placings.some((placing) => placing.place === place),
  );
  const revealed = new Set(places.slice(0, shown));
  const done = shown >= places.length;

  const next = useCallback(
    () => setShown((value) => Math.min(value + 1, places.length)),
    [places.length],
  );
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === ' ' || event.key === 'ArrowRight' || event.key === 'Enter') {
        event.preventDefault();
        next();
      }
      if (event.key === 'ArrowLeft') setShown((value) => Math.max(0, value - 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next]);

  return (
    <Modal opened onClose={onClose} fullScreen withCloseButton={false} padding={0}>
      <div
        ref={stageRef}
        className={classes.stage}
        onClick={next}
        role="button"
        tabIndex={0}
        aria-label={t('podium_next_label')}
      >
        {revealed.has(1) ? <Confetti /> : null}
        <div>
          <div className={classes.title}>{className}</div>
          <div className={classes.subtitle}>{podium.title}</div>
        </div>
        <div className={classes.podium}>
          {COLUMNS.map((place) => {
            const names = podium.placings.filter((placing) => placing.place === place);
            const hidden = !revealed.has(place);
            return (
              <div key={place} className={classes.column}>
                <div className={classes.names} data-hidden={hidden} aria-live="polite">
                  {hidden
                    ? null
                    : names.map((placing) => (
                        <span key={placing.team_id}>{placing.team_name}</span>
                      ))}
                </div>
                <div className={classes.block} data-place={place} data-hidden={hidden}>
                  {names.length > 0 ? place : ''}
                </div>
              </div>
            );
          })}
        </div>
        <Group gap="sm" onClick={(event) => event.stopPropagation()}>
          <Text className={classes.hint}>
            {done ? t('podium_done_hint') : t('podium_next_hint')}
          </Text>
          <Button
            variant="white"
            size="xs"
            leftSection={<IconMaximize size={14} />}
            onClick={() => stageRef.current?.requestFullscreen?.()}
          >
            {t('draw_full_screen_button')}
          </Button>
          <Button variant="subtle" color="gray" size="xs" onClick={onClose}>
            {t('close_button')}
          </Button>
        </Group>
      </div>
    </Modal>
  );
}
