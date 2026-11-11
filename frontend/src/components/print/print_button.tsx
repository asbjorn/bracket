import { Button } from '@mantine/core';
import { IconPrinter } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

/** Prints the page; the button itself and the navigation are not printed. */
export function PrintButton({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <Button
      className="no-print"
      variant="default"
      leftSection={<IconPrinter size={18} />}
      onClick={() => window.print()}
    >
      {label ?? t('print_button')}
    </Button>
  );
}
