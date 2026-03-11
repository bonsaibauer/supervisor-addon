import { useEffect, useState } from 'react';

import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import type { ActivityEvent } from '../../api/types';
import { serverActivity } from '../../api/servers';
import { useI18n } from '../../i18n';
import { formatDateTime } from '../../utils/datetime/formatDateTime';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Table } from '../../components/ui/Table';

const ACTIVITY_LIMIT = 1000;

type ActivityPayload = {
  action_id?: string;
  signal?: string;
  mode?: string;
  program?: string;
  result?: unknown;
  wait?: boolean;
  actor?: string;
  path?: string;
  size?: number;
  filename?: string;
  count?: number;
};

type Translate = (key: string, values?: Record<string, string | number | boolean | null | undefined>) => string;

function actionOutcomeLabel(payload: ActivityPayload, t: Translate): string | null {
  if (typeof payload.result !== 'boolean') {
    return null;
  }
  if (payload.wait === false) {
    return payload.result ? t('activity.outcome.triggered') : t('activity.outcome.trigger_failed');
  }
  return payload.result ? t('activity.outcome.success') : t('activity.outcome.failed');
}

function friendlyActionLabel(item: ActivityEvent, t: Translate): string {
  const payload = (item.payload || {}) as ActivityPayload;
  const actionId = payload.action_id || '';
  const path = typeof payload.path === 'string' ? payload.path.toLowerCase() : '';
  const looksLikeConfig =
    path.includes('server_config') ||
    path.includes('enshrouded_server.json') ||
    path.endsWith('.json') ||
    path.endsWith('.yaml') ||
    path.endsWith('.yml') ||
    path.endsWith('.toml') ||
    path.endsWith('.ini') ||
    path.endsWith('.cfg') ||
    path.endsWith('.conf') ||
    path.endsWith('.env');

  switch (actionId) {
    case 'server.start':
      return t('activity.action.start_server');
    case 'server.stop':
      return t('activity.action.stop_server');
    case 'server.restart_safe':
      return t('activity.action.safe_restart');
    case 'backup.create':
      return t('activity.action.create_backup');
    case 'update.run':
      return t('activity.action.run_update');
    case 'update.force':
      return t('activity.action.force_update');
    default:
      switch (item.event) {
        case 'server.action':
          return actionId ? t('activity.action.run_action_with_id', { action_id: actionId }) : t('activity.action.run_server_action');
        case 'gateway.reload_actions':
          return t('activity.action.reload_actions');
        case 'auth.login':
          return t('activity.action.login');
        case 'auth.change_password':
          return t('activity.action.change_password');
        case 'file.write':
          return looksLikeConfig ? t('activity.action.save_config') : t('activity.action.edit_file');
        case 'file.read':
          return looksLikeConfig ? t('activity.action.load_config') : t('activity.action.read_file');
        case 'file.create_folder':
          return t('activity.action.create_folder');
        case 'file.rename':
          return t('activity.action.rename_item');
        case 'file.delete':
          return t('activity.action.delete_item');
        case 'file.upload':
          return t('activity.action.upload_file');
        case 'file.download':
          return t('activity.action.download_file');
        default:
          return item.event || t('activity.action.event_fallback');
      }
  }
}

function friendlyDetails(item: ActivityEvent, t: Translate): string {
  const payload = (item.payload || {}) as ActivityPayload;
  const parts: string[] = [];
  const event = item.event || '';

  const outcomeLabel = actionOutcomeLabel(payload, t);
  if (outcomeLabel) {
    parts.push(outcomeLabel);
  }
  if (event.startsWith('file.')) {
    if (typeof payload.path === 'string' && payload.path.trim()) {
      parts.push(t('activity.details.path', { path: payload.path }));
    }
    if (typeof payload.filename === 'string' && payload.filename.trim()) {
      parts.push(t('activity.details.file', { filename: payload.filename }));
    }
    if (typeof payload.size === 'number' && Number.isFinite(payload.size)) {
      parts.push(t('activity.details.size_bytes', { size: payload.size }));
    }
    if (typeof payload.count === 'number' && Number.isFinite(payload.count)) {
      parts.push(t('activity.details.count', { count: payload.count }));
    }
    if (typeof payload.actor === 'string' && payload.actor.trim()) {
      parts.push(t('activity.details.by', { actor: payload.actor }));
    }
  } else {
    if (typeof payload.action_id === 'string' && payload.action_id.trim()) {
      parts.push(t('activity.details.action', { action_id: payload.action_id }));
    }
    if (typeof payload.signal === 'string' && payload.signal.trim()) {
      parts.push(t('activity.details.signal', { signal: payload.signal }));
    }
    if (typeof payload.mode === 'string' && payload.mode.trim()) {
      parts.push(t('activity.details.mode', { mode: payload.mode }));
    }
    if (typeof payload.program === 'string' && payload.program.trim()) {
      parts.push(t('activity.details.program', { program: payload.program }));
    }
    if (typeof payload.actor === 'string' && payload.actor.trim()) {
      parts.push(t('activity.details.by', { actor: payload.actor }));
    }
  }
  if (typeof payload.wait === 'boolean') {
    parts.push(payload.wait ? t('activity.details.waited_yes') : t('activity.details.waited_no'));
  }

  if (!parts.length) {
    return JSON.stringify(item.payload || {});
  }

  return parts.join(' | ');
}

export function ActivityPage() {
  const serverId = DEFAULT_SERVER_ID;
  const { can } = useAuth();
  const { language, timezone, t } = useI18n();
  const canRead = can('activity.read', serverId);

  const [items, setItems] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  async function load() {
    if (!canRead) {
      setError(t('activity.page.error.read_forbidden'));
      return;
    }

    setLoading(true);
    setError('');
    try {
      const response = await serverActivity(serverId, ACTIVITY_LIMIT);
      setItems(response.items || []);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('activity.page.error.load_failed'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [serverId, canRead]);

  return (
    <section className="page">
      <Card
        title={t('activity.page.title')}
        subtitle={t('activity.page.subtitle', { server_id: serverId })}
        actions={
          <Button variant="ghost" onClick={load} loading={loading}>
            {t('common.refresh')}
          </Button>
        }
      >
        {error && <p className="hint hint--error">{error}</p>}

        <div className="activity-table-wrap">
          <Table
            rows={items}
            emptyText={loading ? t('activity.page.loading') : t('activity.page.empty')}
            columns={[
              {
                key: 'time',
                title: t('activity.table.time'),
                render: (row) => {
                  const item = row as ActivityEvent & { timestamp?: number | string };
                  const ts = Number(item.ts ?? item.timestamp ?? 0);
                  return ts > 0 ? formatDateTime(ts * 1000, language, timezone) : t('common.na');
                },
              },
              {
                key: 'action',
                title: t('activity.table.action'),
                render: (row) => friendlyActionLabel(row as ActivityEvent, t),
              },
              {
                key: 'details',
                title: t('activity.table.details'),
                render: (row) => friendlyDetails(row as ActivityEvent, t),
              },
            ]}
          />
        </div>
      </Card>
    </section>
  );
}
