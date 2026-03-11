import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { useI18n } from '../../i18n';

export function OptionsPage() {
  const serverId = DEFAULT_SERVER_ID;
  const { updatePreferences } = useAuth();
  const { language, timezone, languages, t } = useI18n();
  const [selectedLanguage, setSelectedLanguage] = useState(language);
  const [selectedTimezone, setSelectedTimezone] = useState(timezone);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  const selectedLanguageInfo = useMemo(
    () => languages.find((entry) => entry.code === selectedLanguage) || null,
    [languages, selectedLanguage]
  );

  const timezoneOptions = selectedLanguageInfo?.timezones || [];

  const isDirty = selectedLanguage !== language || selectedTimezone !== timezone;

  useEffect(() => {
    setSelectedLanguage(language);
  }, [language]);

  useEffect(() => {
    const languageInfo = languages.find((entry) => entry.code === language);
    if (!languageInfo) return;
    if (languageInfo.timezones.includes(timezone)) {
      setSelectedTimezone(timezone);
      return;
    }
    setSelectedTimezone(languageInfo.default_timezone);
  }, [language, timezone, languages]);

  function onLanguageChange(nextLanguage: string) {
    setSelectedLanguage(nextLanguage);
    setError('');
    setMessage('');

    const nextLanguageInfo = languages.find((entry) => entry.code === nextLanguage);
    if (!nextLanguageInfo) return;
    setSelectedTimezone((previous) =>
      nextLanguageInfo.timezones.includes(previous) ? previous : nextLanguageInfo.default_timezone
    );
  }

  function onTimezoneChange(nextTimezone: string) {
    setSelectedTimezone(nextTimezone);
    setError('');
    setMessage('');
  }

  function onReset() {
    setSelectedLanguage(language);
    const currentLanguageInfo = languages.find((entry) => entry.code === language);
    if (currentLanguageInfo && currentLanguageInfo.timezones.includes(timezone)) {
      setSelectedTimezone(timezone);
    } else {
      setSelectedTimezone(currentLanguageInfo?.default_timezone || timezone);
    }
    setError('');
    setMessage('');
  }

  async function onSave() {
    if (!selectedLanguageInfo) return;
    const timezoneToSave = selectedLanguageInfo.timezones.includes(selectedTimezone)
      ? selectedTimezone
      : selectedLanguageInfo.default_timezone;

    setBusy(true);
    setError('');
    setMessage('');
    try {
      await updatePreferences({
        language: selectedLanguage,
        timezone: timezoneToSave,
      });
      setMessage(t('options.page.saved'));
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('options.page.error.update_failed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <Card
        title={t('options.page.title')}
        subtitle={t('options.page.subtitle', { server_id: serverId })}
        actions={
          <div className="row-actions">
            <Button variant="ghost" onClick={onReset} disabled={!isDirty || busy}>
              {t('options.page.reset')}
            </Button>
            <Button variant="primary" loading={busy} onClick={onSave} disabled={!isDirty || !selectedLanguageInfo}>
              {t('options.page.save')}
            </Button>
          </div>
        }
      >
        <div className="options-grid">
          <label className="form-field">
            {t('options.page.language.label')}
            <select
              value={selectedLanguage}
              onChange={(event) => onLanguageChange(event.target.value)}
              disabled={busy}
              aria-label={t('options.page.language.label')}
            >
              {languages.map((entry) => (
                <option key={entry.code} value={entry.code}>
                  {entry.native_label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            {t('options.page.timezone.label')}
            <select
              value={selectedTimezone}
              onChange={(event) => onTimezoneChange(event.target.value)}
              disabled={busy || timezoneOptions.length === 0}
              aria-label={t('options.page.timezone.label')}
            >
              {timezoneOptions.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                  {selectedLanguageInfo?.default_timezone === zone ? ` (${t('options.page.timezone.default')})` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        {selectedLanguageInfo && (
          <p className="hint">
            {t('options.page.timezone.default_hint', {
              timezone: selectedLanguageInfo.default_timezone,
            })}
          </p>
        )}
        {error && <p className="hint hint--error">{error}</p>}
        {message && <p className="hint">{message}</p>}
      </Card>
    </section>
  );
}
