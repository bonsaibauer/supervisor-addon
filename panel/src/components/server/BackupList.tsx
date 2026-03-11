import { useEffect, useState } from 'react';

import { useAuth } from '../../app/auth';
import type { FileListItem } from '../../api/types';
import { checkBackupPreconditions, downloadBackupFile, listBackupFiles, triggerBackup } from '../../api/backups';
import { useI18n } from '../../i18n';
import { formatDateTime } from '../../utils/datetime/formatDateTime';
import { Button } from '../ui/Button';
import { Table } from '../ui/Table';

interface Props {
  serverId: string;
}

export function BackupList({ serverId }: Props) {
  const { can } = useAuth();
  const { language, timezone, t } = useI18n();
  const canControl = can('server.control', serverId);

  const [items, setItems] = useState<FileListItem[]>([]);
  const [root, setRoot] = useState<string | undefined>(undefined);
  const [path, setPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busyAction, setBusyAction] = useState('');
  const [error, setError] = useState('');
  const [backupReady, setBackupReady] = useState(false);
  const [backupHint, setBackupHint] = useState('');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  async function load() {
    setLoading(true);
    setError('');
    try {
      const response = await listBackupFiles(serverId);
      setRoot(response.root);
      setPath(response.path);
      setItems(response.items);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('backups.error.load_failed'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [serverId]);

  useEffect(() => {
    let active = true;
    void checkBackupPreconditions(serverId)
      .then((result) => {
        if (!active) return;
        setBackupReady(result.ok);
        setBackupHint(result.message);
      })
      .catch((err) => {
        if (!active) return;
        setBackupReady(false);
        setBackupHint(err instanceof Error ? localizeErrorMessage(err.message) : t('backups.error.preflight_failed'));
      });
    return () => {
      active = false;
    };
  }, [serverId]);

  async function createNow() {
    if (!canControl) {
      setError(t('backups.error.create_forbidden'));
      return;
    }

    setCreating(true);
    setError('');
    try {
      await triggerBackup(serverId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('backups.error.request_failed'));
    } finally {
      setCreating(false);
    }
  }

  async function onDownload(item: FileListItem) {
    setError('');
    setBusyAction(`download:${item.path}`);
    try {
      const { blob, filename } = await downloadBackupFile(serverId, item.path, root);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename || item.name || 'backup.zip';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('backups.error.download_failed'));
    } finally {
      setBusyAction('');
    }
  }

  return (
    <div>
      {!canControl && <p className="hint">{t('backups.read_only_hint')}</p>}

      <div className="row-actions">
        <Button variant="primary" loading={creating} onClick={createNow} disabled={!canControl || !backupReady}>
          {t('backups.action.create')}
        </Button>
        <Button variant="ghost" loading={loading} onClick={load}>
          {t('common.refresh')}
        </Button>
        {path && <span className="chip chip--muted">{t('backups.folder', { path })}</span>}
        {root && <span className="chip chip--muted">{t('backups.root', { root })}</span>}
      </div>

      {error && <p className="hint hint--error">{error}</p>}
      {!backupReady && backupHint && <p className="hint hint--error">{localizeErrorMessage(backupHint)}</p>}

      <Table
        rows={items}
        emptyText={loading ? t('backups.loading') : t('backups.empty')}
        columns={[
          {
            key: 'name',
            title: t('backups.table.filename'),
            render: (row) => (row as FileListItem).name,
          },
          {
            key: 'size',
            title: t('backups.table.size'),
            render: (row) => `${(row as FileListItem).size} B`,
          },
          {
            key: 'modified',
            title: t('backups.table.modified'),
            render: (row) => formatDateTime((row as FileListItem).modified_at * 1000, language, timezone),
          },
          {
            key: 'path',
            title: t('backups.table.path'),
            render: (row) => (row as FileListItem).path,
          },
          {
            key: 'actions',
            title: t('backups.table.actions'),
            render: (row) => {
              const item = row as FileListItem;
              return (
                <div className="row-actions">
                  <Button
                    variant="ghost"
                    loading={busyAction === `download:${item.path}`}
                    onClick={() => onDownload(item)}
                  >
                    {t('backups.action.download')}
                  </Button>
                </div>
              );
            },
          },
        ]}
      />
    </div>
  );
}
