import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../app/auth';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useI18n } from '../i18n';

function validateNewPassword(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
  t: (key: string) => string
): string | null {
  if (newPassword.length < 8) return t('validation.password.min_length');
  if (newPassword !== confirmPassword) return t('validation.password.mismatch');
  if (newPassword === currentPassword) return t('validation.password.same_as_current');
  return null;
}

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const { user, mustChangePassword, changePassword, logout } = useAuth();
  const { t } = useI18n();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  useEffect(() => {
    if (!mustChangePassword) {
      navigate('/console', { replace: true });
    }
  }, [mustChangePassword, navigate]);

  if (!mustChangePassword) return null;

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    const validationError = validateNewPassword(currentPassword, newPassword, confirmPassword, t);
    if (validationError) {
      setError(validationError);
      return;
    }

    setBusy(true);
    try {
      await changePassword(currentPassword, newPassword);
      navigate('/console', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('auth.change_password.error'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <Card
        title={t('auth.change_password.required_title')}
        subtitle={t('auth.change_password.user', { username: user?.username || t('auth.change_password.unknown_user') })}
      >
        <p className="hint hint--error">{t('auth.change_password.warning')}</p>
        <form className="login-form" onSubmit={onSubmit}>
          <label className="form-field">
            <span>{t('auth.change_password.current_password')}</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label className="form-field">
            <span>{t('auth.change_password.new_password')}</span>
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <label className="form-field">
            <span>{t('auth.change_password.confirm_password')}</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <div className="row-actions">
            <Button variant="primary" loading={busy} type="submit">
              {t('auth.change_password.submit')}
            </Button>
            <Button variant="ghost" type="button" onClick={() => void logout()} disabled={busy}>
              {t('auth.change_password.logout')}
            </Button>
          </div>
        </form>
        <p className="hint">{t('auth.change_password.rules')}</p>
        {error && <p className="hint hint--error">{error}</p>}
      </Card>
    </section>
  );
}
