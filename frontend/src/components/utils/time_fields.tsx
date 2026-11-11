import { DateTimePicker, DateTimePickerProps, TimePicker, TimePickerProps } from '@mantine/dates';

// All time inputs in the app use the 24-hour clock, whatever the browser's language. The
// browser's own <input type="time"> can't be forced to 24 hours, so Mantine's pickers are used.

/** A time of day as "HH:mm". */
export function TimeField(props: Omit<TimePickerProps, 'format'>) {
  return <TimePicker format="24h" withDropdown {...props} />;
}

/** A date and time, shown as e.g. "20.11.2026 09:00". */
export function DateTimeField({ timePickerProps, ...props }: DateTimePickerProps) {
  return (
    <DateTimePicker
      valueFormat="DD.MM.YYYY HH:mm"
      timePickerProps={{ ...timePickerProps, format: '24h' }}
      {...props}
    />
  );
}
