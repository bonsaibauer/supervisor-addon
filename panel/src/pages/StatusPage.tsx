import { Link, useParams } from 'react-router-dom';
import { useI18n } from '../i18n';

type StatusTheme = 'warning' | 'danger' | 'neutral';

interface StatusDefinition {
  code: string;
  title_key: string;
  message_key: string;
  hint_key: string;
  theme: StatusTheme;
}

const DEFAULT_STATUS: StatusDefinition = {
  code: '500',
  title_key: 'status.500.title',
  message_key: 'status.500.message',
  hint_key: 'status.500.hint',
  theme: 'danger',
};

const STATUS_MAP: Record<string, StatusDefinition> = {
  '400': {
    code: '400',
    title_key: 'status.400.title',
    message_key: 'status.400.message',
    hint_key: 'status.400.hint',
    theme: 'warning',
  },
  '401': {
    code: '401',
    title_key: 'status.401.title',
    message_key: 'status.401.message',
    hint_key: 'status.401.hint',
    theme: 'warning',
  },
  '403': {
    code: '403',
    title_key: 'status.403.title',
    message_key: 'status.403.message',
    hint_key: 'status.403.hint',
    theme: 'danger',
  },
  '404': {
    code: '404',
    title_key: 'status.404.title',
    message_key: 'status.404.message',
    hint_key: 'status.404.hint',
    theme: 'neutral',
  },
  '405': {
    code: '405',
    title_key: 'status.405.title',
    message_key: 'status.405.message',
    hint_key: 'status.405.hint',
    theme: 'warning',
  },
  '408': {
    code: '408',
    title_key: 'status.408.title',
    message_key: 'status.408.message',
    hint_key: 'status.408.hint',
    theme: 'warning',
  },
  '409': {
    code: '409',
    title_key: 'status.409.title',
    message_key: 'status.409.message',
    hint_key: 'status.409.hint',
    theme: 'warning',
  },
  '413': {
    code: '413',
    title_key: 'status.413.title',
    message_key: 'status.413.message',
    hint_key: 'status.413.hint',
    theme: 'warning',
  },
  '415': {
    code: '415',
    title_key: 'status.415.title',
    message_key: 'status.415.message',
    hint_key: 'status.415.hint',
    theme: 'warning',
  },
  '429': {
    code: '429',
    title_key: 'status.429.title',
    message_key: 'status.429.message',
    hint_key: 'status.429.hint',
    theme: 'warning',
  },
  '500': {
    code: '500',
    title_key: 'status.500.title',
    message_key: 'status.500.message',
    hint_key: 'status.500.hint',
    theme: 'danger',
  },
  '502': {
    code: '502',
    title_key: 'status.502.title',
    message_key: 'status.502.message',
    hint_key: 'status.502.hint',
    theme: 'danger',
  },
  '503': {
    code: '503',
    title_key: 'status.503.title',
    message_key: 'status.503.message',
    hint_key: 'status.503.hint',
    theme: 'danger',
  },
  'https-required': {
    code: 'HTTPS',
    title_key: 'status.https_required.title',
    message_key: 'status.https_required.message',
    hint_key: 'status.https_required.hint',
    theme: 'warning',
  },
};

function resolveStatus(key: string | undefined): StatusDefinition {
  if (!key) return DEFAULT_STATUS;
  return STATUS_MAP[key] ?? {
    code: key.toUpperCase(),
    title_key: 'status.generic.title',
    message_key: 'status.generic.message',
    hint_key: 'status.generic.hint',
    theme: 'neutral',
  };
}

export function StatusPage() {
  const { code } = useParams<{ code: string }>();
  const { t } = useI18n();
  const status = resolveStatus(code);

  return (
    <section className={`status-page status-page--${status.theme}`}>
      <div className="status-card">
        <div className="status-card__rail" />
        <p className="status-card__code">{status.code}</p>
        <h1 className="status-card__title">{t(status.title_key)}</h1>
        <p className="status-card__message">{t(status.message_key)}</p>
        <p className="status-card__hint">{t(status.hint_key)}</p>
        <div className="status-card__actions">
          <Link className="btn btn--primary" to="/login">
            {t('status.action.login')}
          </Link>
          <Link className="btn btn--secondary" to="/console">
            {t('status.action.console')}
          </Link>
          <button className="btn btn--ghost" type="button" onClick={() => window.location.reload()}>
            {t('status.action.retry')}
          </button>
        </div>
      </div>
    </section>
  );
}
