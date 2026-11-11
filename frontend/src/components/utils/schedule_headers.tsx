import { Center, Divider, Text } from '@mantine/core';
import React from 'react';

import { Day, formatTime, isSameDateTimeDay } from '@components/utils/datetime';

/**
 * Headers to show before a match in a chronological schedule: a day header when the schedule
 * spans multiple days and a new day starts, and a time header when the start time changes.
 */
export function getScheduleHeaders({
  startTime,
  previousStartTime,
  multipleDays,
  keySuffix,
}: {
  startTime: string;
  previousStartTime: string | null;
  multipleDays: boolean;
  keySuffix: string | number;
}): React.JSX.Element[] {
  const headers: React.JSX.Element[] = [];
  const isNewDay = previousStartTime == null || !isSameDateTimeDay(previousStartTime, startTime);

  if (multipleDays && isNewDay) {
    headers.push(
      <Divider
        key={`day-${keySuffix}`}
        mt="xl"
        labelPosition="center"
        label={
          <Text size="lg" fw={700}>
            <Day datetime={startTime} />
          </Text>
        }
      />,
    );
  }

  if (isNewDay || formatTime(startTime) !== formatTime(previousStartTime ?? startTime)) {
    headers.push(
      <Center mt="md" key={`time-${keySuffix}`}>
        <Text size="xl" fw={800}>
          {formatTime(startTime)}
        </Text>
      </Center>,
    );
  }

  return headers;
}
