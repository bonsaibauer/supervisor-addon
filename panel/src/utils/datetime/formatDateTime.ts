export function formatDateTime(value: number | Date, language: string, timezone: string): string {
  const input = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(input.getTime())) {
    return '-';
  }

  try {
    return new Intl.DateTimeFormat(language, {
      dateStyle: 'medium',
      timeStyle: 'medium',
      timeZone: timezone,
    }).format(input);
  } catch {
    return '-';
  }
}
