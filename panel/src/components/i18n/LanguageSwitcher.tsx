import { useEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from '../../app/auth';
import { useI18n } from '../../i18n';

export function LanguageSwitcher() {
  const { language, languages, t } = useI18n();
  const { updatePreferences } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  const current = useMemo(() => languages.find((entry) => entry.code === language), [language, languages]);
  const resolveFlagClass = (flag: string): string | null => {
    const code = flag.trim().toLowerCase().replace(/^fi-/, '');
    if (!/^[a-z]{2,3}(?:-[a-z0-9]{2,4})?$/.test(code)) return null;
    return `fi fi-${code}`;
  };

  async function onChange(nextLanguage: string) {
    if (!nextLanguage || nextLanguage === language) return;
    setBusy(true);
    setError('');

    const languageInfo = languages.find((entry) => entry.code === nextLanguage);
    if (!languageInfo) {
      setBusy(false);
      return;
    }
    const timezone = languageInfo.default_timezone;

    try {
      await updatePreferences({ language: nextLanguage, timezone });
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('topnav.language_update_failed'));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!open) return undefined;

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }

    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!current) return null;
  const currentFlagClass = resolveFlagClass(current.flag);

  return (
    <div className="language-switcher" title={error || current.native_label} ref={rootRef}>
      <button
        type="button"
        className="language-switcher__trigger"
        onClick={() => setOpen((prev) => !prev)}
        disabled={busy}
        aria-label={t('topnav.language')}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={current.native_label}
      >
        {currentFlagClass ? (
          <span className={`${currentFlagClass} language-switcher__flag`} aria-hidden="true" />
        ) : (
          <span className="language-switcher__flag language-switcher__flag--fallback" aria-hidden="true">
            {current.flag}
          </span>
        )}
      </button>
      {open && (
        <div className="language-switcher__menu" role="listbox" aria-label={t('topnav.language')}>
          {languages.map((entry) => {
            const flagClass = resolveFlagClass(entry.flag);
            return (
              <button
                key={entry.code}
                type="button"
                className={`language-switcher__option${entry.code === language ? ' is-active' : ''}`}
                onClick={() => {
                  setOpen(false);
                  void onChange(entry.code);
                }}
                role="option"
                aria-selected={entry.code === language}
                aria-label={entry.native_label}
                title={entry.native_label}
                disabled={busy}
              >
                {flagClass ? (
                  <span className={`${flagClass} language-switcher__flag`} aria-hidden="true" />
                ) : (
                  <span className="language-switcher__flag language-switcher__flag--fallback" aria-hidden="true">
                    {entry.flag}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
