import { useState } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../app/auth';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useI18n } from '../i18n';

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const { t } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('auth.login.error'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="login-page">
      <Card title={t('auth.login.title')} subtitle={t('auth.login.subtitle')}>
        <form className="login-form" onSubmit={onSubmit}>
          <label className="form-field">
            <span>{t('auth.login.username')}</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
          </label>

          <label className="form-field">
            <span>{t('auth.login.password')}</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <Button variant="primary" loading={busy} type="submit">
            {t('auth.login.submit')}
          </Button>

          {error && <p className="hint hint--error">{error}</p>}
        </form>
      </Card>
    </section>
  );
}

