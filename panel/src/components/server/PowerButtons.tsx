import { useEffect, useState } from 'react';

import { checkBackupPreconditions, triggerBackup } from '../../api/backups';
import { runUpdate, sendPowerSignal } from '../../api/servers';
import { useAuth } from '../../app/auth';
import { useI18n } from '../../i18n';
import { Button } from '../ui/Button';

interface Props {
  serverId: string;
  onDone?: () => void;
  showBackupWarningInline?: boolean;
  onBackupWarningChange?: (warning: string) => void;
}

export function PowerButtons({ serverId, onDone, showBackupWarningInline = true, onBackupWarningChange }: Props) {
  const { can } = useAuth();
  const { t } = useI18n();
  const canControl = can('server.control', serverId);

  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('');
  const [backupReady, setBackupReady] = useState<boolean>(false);
  const [backupHint, setBackupHint] = useState<string>('');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  useEffect(() => {
    let active = true;
    if (!canControl) return;
    void checkBackupPreconditions(serverId)
      .then((result) => {
        if (!active) return;
        setBackupReady(result.ok);
        setBackupHint(result.message);
        onBackupWarningChange?.(!result.ok ? result.message : '');
      })
      .catch((error) => {
        if (!active) return;
        setBackupReady(false);
        const message = error instanceof Error ? localizeErrorMessage(error.message) : t('power.error.preflight_failed');
        setBackupHint(message);
        onBackupWarningChange?.(message);
      });
    return () => {
      active = false;
    };
  }, [serverId, canControl, onBackupWarningChange]);

  async function run(actionId: string, successKey: string, fn: () => Promise<unknown>) {
    setBusy(actionId);
    setMessage('');
    try {
      await fn();
      setMessage(t(successKey));
      onDone?.();
    } catch (error) {
      setMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('power.error.request_failed'));
    } finally {
      setBusy(null);
    }
  }

  if (!canControl) {
    return <p className="hint">{t('power.read_only_hint')}</p>;
  }

  return (
    <>
      <div className="power-grid">
        <Button variant="primary" loading={busy === 'start'} onClick={() => run('start', 'power.success.start_queued', () => sendPowerSignal(serverId, 'start'))}>
          {t('power.action.start')}
        </Button>
        <Button variant="secondary" loading={busy === 'restart'} onClick={() => run('restart', 'power.success.restart_queued', () => sendPowerSignal(serverId, 'restart_safe'))}>
          {t('power.action.restart')}
        </Button>
        <Button variant="danger" loading={busy === 'stop'} onClick={() => run('stop', 'power.success.stop_queued', () => sendPowerSignal(serverId, 'stop'))}>
          {t('power.action.stop')}
        </Button>
        <Button
          loading={busy === 'backup'}
          onClick={() => run('backup', 'power.success.backup_queued', () => triggerBackup(serverId))}
          disabled={!backupReady}
        >
          {t('power.action.backup')}
        </Button>
        <Button loading={busy === 'update'} onClick={() => run('update', 'power.success.update_queued', () => runUpdate(serverId, 'run'))}>
          {t('power.action.update')}
        </Button>
        <Button loading={busy === 'force_update'} onClick={() => run('force_update', 'power.success.force_update_queued', () => runUpdate(serverId, 'force'))}>
          {t('power.action.force_update')}
        </Button>
      </div>
      {message && <p className="hint">{message}</p>}
      {showBackupWarningInline && !backupReady && backupHint && (
        <>
          <div className="runtime-divider" />
          <p className="runtime-warning-title">{t('power.warning.title')}</p>
          <p className="hint hint--error runtime-warning-text">{localizeErrorMessage(backupHint)}</p>
        </>
      )}
    </>
  );
}
