import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { getServer } from '../../api/servers';
import type { EnvCatalogItem, ServerDetails } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Table } from '../../components/ui/Table';
import { useI18n } from '../../i18n';

type EnvGroup = {
  id: string;
  title: string;
  subtitle: string;
  items: EnvCatalogItem[];
};
type Translate = (key: string, values?: Record<string, string | number | boolean | null | undefined>) => string;

const SERVER_ROLE_KEY_PATTERN = /^SERVER_ROLE_(\d+)_(.+)$/;
const SERVER_ROLE_FIELD_ORDER: string[] = [
  'NAME',
  'PASSWORD',
  'CAN_KICK_BAN',
  'CAN_ACCESS_INVENTORIES',
  'CAN_EDIT_WORLD',
  'CAN_EDIT_BASE',
  'CAN_EXTEND_BASE',
  'RESERVED_SLOTS',
];

function envCatalog(server: ServerDetails | null): EnvCatalogItem[] {
  if (!server) return [];
  const raw = (server.files as Record<string, unknown>).env_catalog;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) return null;
      const record = item as Record<string, unknown>;
      const key = typeof record.key === 'string' ? record.key.trim() : '';
      if (!key) return null;
      return {
        key,
        is_set: Boolean(record.is_set),
        deprecated: Boolean(record.deprecated),
        status: typeof record.status === 'string' ? record.status : undefined,
        value: record.value == null ? null : String(record.value),
        default_value: record.default_value == null ? null : String(record.default_value),
      } as EnvCatalogItem;
    })
    .filter((item): item is EnvCatalogItem => Boolean(item))
    .sort((a, b) => a.key.localeCompare(b.key));
}

function groupEnv(items: EnvCatalogItem[], t: Translate): EnvGroup[] {
  const gameSettingsItems = items
    .filter((item) => item.key.startsWith('SERVER_GS_'))
    .sort((a, b) => {
      if (a.key === 'SERVER_GS_PRESET' && b.key !== 'SERVER_GS_PRESET') return -1;
      if (a.key !== 'SERVER_GS_PRESET' && b.key === 'SERVER_GS_PRESET') return 1;
      return a.key.localeCompare(b.key);
    });

  const roleItems = items.filter((item) => item.key.startsWith('SERVER_ROLE_'));
  const rolesByIndex = new Map<number, EnvCatalogItem[]>();
  roleItems.forEach((item) => {
    const match = SERVER_ROLE_KEY_PATTERN.exec(item.key);
    if (!match) return;
    const index = Number.parseInt(match[1], 10);
    if (Number.isNaN(index)) return;
    const bucket = rolesByIndex.get(index) || [];
    bucket.push(item);
    rolesByIndex.set(index, bucket);
  });
  const roleGroups: EnvGroup[] = [...rolesByIndex.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([index, roleGroupItems]) => {
      const sortedItems = [...roleGroupItems].sort((a, b) => {
        const aMatch = SERVER_ROLE_KEY_PATTERN.exec(a.key);
        const bMatch = SERVER_ROLE_KEY_PATTERN.exec(b.key);
        const aSuffix = aMatch ? aMatch[2] : a.key;
        const bSuffix = bMatch ? bMatch[2] : b.key;
        const aPos = SERVER_ROLE_FIELD_ORDER.indexOf(aSuffix);
        const bPos = SERVER_ROLE_FIELD_ORDER.indexOf(bSuffix);
        if (aPos >= 0 && bPos >= 0) return aPos - bPos;
        if (aPos >= 0) return -1;
        if (bPos >= 0) return 1;
        return aSuffix.localeCompare(bSuffix);
      });
      return {
        id: `server-role-${index}`,
        title: t('env.group.role.title', { index }),
        subtitle: t('env.group.role.subtitle'),
        items: sortedItems,
      };
    });

  const groups: Array<{
    id: string;
    title: string;
    subtitle: string;
    match: (key: string) => boolean;
    alwaysShow?: boolean;
  }> = [
    {
      id: 'server',
      title: t('env.group.server.title'),
      subtitle: t('env.group.server.subtitle'),
      match: (key) =>
        key.startsWith('SERVER_') &&
        !key.startsWith('SERVER_ROLE_') &&
        !key.startsWith('SERVER_GS_'),
      alwaysShow: true,
    },
    {
      id: 'game-settings-slot',
      title: '',
      subtitle: '',
      match: () => false,
    },
    {
      id: 'role-slot',
      title: '',
      subtitle: '',
      match: () => false,
    },
    {
      id: 'automation',
      title: t('env.group.automation.title'),
      subtitle: t('env.group.automation.subtitle'),
      match: (key) =>
        key.startsWith('UPDATE_') ||
        key.startsWith('BACKUP_') ||
        key.startsWith('RESTART_') ||
        key === 'BOOTSTRAP_HOOK',
      alwaysShow: true,
    },
    {
      id: 'runtime',
      title: t('env.group.runtime.title'),
      subtitle: t('env.group.runtime.subtitle'),
      match: (key) =>
        key === 'PUID' ||
        key === 'PGID' ||
        key === 'GAME_BRANCH' ||
        key === 'STEAMCMD_ARGS' ||
        key === 'STEAM_API_PUBLIC_IP' ||
        key === 'STEAM_API_KEY' ||
        key === 'WINEDEBUG' ||
        key === 'STEAM_COMPAT_DATA_PATH',
      alwaysShow: true,
    },
    {
      id: 'gateway',
      title: t('env.group.gateway.title'),
      subtitle: t('env.group.gateway.subtitle'),
      match: (key) => key.startsWith('SUPERVISOR_GATEWAY_'),
      alwaysShow: true,
    },
    {
      id: 'addon',
      title: t('env.group.addon.title'),
      subtitle: t('env.group.addon.subtitle'),
      match: (key) => key.startsWith('SUPERVISOR_ADDON_'),
      alwaysShow: true,
    },
    {
      id: 'supervisor-addon-user',
      title: t('env.group.supervisor_addon_user.title'),
      subtitle: t('env.group.supervisor_addon_user.subtitle'),
      match: (key) => key.startsWith('AUTH_TEMPLATE_'),
    },
  ];

  const remaining = [...items];
  const result: EnvGroup[] = [];
  for (const group of groups) {
    if (group.id === 'game-settings-slot') {
      result.push({
        id: 'game-settings',
        title: t('env.group.game_settings.title'),
        subtitle: t('env.group.game_settings.subtitle'),
        items: gameSettingsItems,
      });
      continue;
    }
    if (group.id === 'role-slot') {
      result.push(...roleGroups);
      continue;
    }
    const groupItems = remaining.filter((item) => group.match(item.key));
    if (!groupItems.length && !group.alwaysShow) continue;
    result.push({
      id: group.id,
      title: group.title,
      subtitle: group.subtitle,
      items: groupItems,
    });
  }

  const matched = new Set(result.flatMap((group) => group.items.map((item) => item.key)));
  const otherItems = items.filter((item) => !matched.has(item.key));
  if (otherItems.length) {
    result.push({
      id: 'other',
      title: t('env.group.other.title'),
      subtitle: t('env.group.other.subtitle'),
      items: otherItems,
    });
  }

  return result;
}

export function EnvPage() {
  const serverId = DEFAULT_SERVER_ID;
  const { can } = useAuth();
  const { t } = useI18n();
  const canRead = can('server.read', serverId);

  const [server, setServer] = useState<ServerDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const catalog = useMemo(() => envCatalog(server), [server]);
  const grouped = useMemo(() => groupEnv(catalog, t), [catalog, t]);
  const setCount = useMemo(() => catalog.filter((item) => item.is_set).length, [catalog]);
  const startupConfigPath = useMemo(() => {
    if (!server) return '';
    const raw = server.files as Record<string, unknown>;
    return typeof raw.startup_config === 'string' ? raw.startup_config.trim() : '';
  }, [server]);
  const startupJsonLoaded = useMemo(() => {
    if (!server) return true;
    const raw = server.files as Record<string, unknown>;
    return raw.startup_json_loaded === false ? false : true;
  }, [server]);
  const startupJsonError = useMemo(() => {
    if (!server) return '';
    const raw = server.files as Record<string, unknown>;
    return typeof raw.startup_json_error === 'string' ? raw.startup_json_error.trim() : '';
  }, [server]);

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  function isGroupOpenByDefault(groupId: string): boolean {
    if (groupId === 'game-settings' || groupId === 'server') return true;
    if (groupId.startsWith('server-role-')) return true;
    return false;
  }

  async function load() {
    if (!canRead) return;
    setLoading(true);
    setError('');
    try {
      const response = await getServer(serverId);
      setServer(response);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('env.page.error.load_failed'));
      setServer(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [serverId, canRead]);

  if (!canRead) {
    return (
      <section className="page">
        <Card title={t('env.page.title')} subtitle={t('common.server_subtitle', { server_id: serverId })}>
          <p className="hint hint--error">{t('env.page.error.read_forbidden')}</p>
        </Card>
      </section>
    );
  }

  return (
    <section className="page">
      <Card
        title={t('env.page.title')}
        subtitle={t('common.server_subtitle', { server_id: serverId })}
        actions={
          <Button variant="ghost" onClick={load} loading={loading}>
            {t('common.refresh')}
          </Button>
        }
      >
        <p className="hint">
          {t('env.page.set_count', { set_count: setCount, total_count: catalog.length })}
        </p>
        {!startupJsonLoaded && startupConfigPath && (
          <p className="hint hint--error">
            {startupJsonError || t('news.item.startup_config_missing.message', { startup_config_path: startupConfigPath })}
          </p>
        )}
        {error && <p className="hint hint--error">{error}</p>}
      </Card>

      {grouped.map((group) => {
        return (
          <Card key={group.id}>
            <details className="env-group" open={isGroupOpenByDefault(group.id)}>
              <summary className="env-group__summary">
                <div>
                  <h3 className="env-group__title">{group.title}</h3>
                  <p className="env-group__subtitle">{group.subtitle}</p>
                </div>
              </summary>
              <div className="env-group__content">
                <Table
                  rows={group.items}
                  emptyText={t('env.page.empty_group')}
                  columns={[
                    {
                      key: 'key',
                      title: t('env.table.key'),
                      render: (row) => <code>{(row as EnvCatalogItem).key}</code>,
                    },
                    {
                      key: 'status',
                      title: t('env.table.status'),
                      render: (row) => {
                        const item = row as EnvCatalogItem;
                        const rawStatus = item.status;
                        const status = rawStatus === 'deprecated' || rawStatus === 'automatic' || rawStatus === 'set' || rawStatus === 'unset'
                          ? rawStatus
                          : item.deprecated
                            ? 'deprecated'
                            : item.is_set
                              ? 'set'
                              : 'unset';
                        const statusClass = status === 'deprecated'
                          ? 'status-pill status-pill--warn'
                          : status === 'automatic'
                            ? 'status-pill status-pill--neutral'
                            : status === 'set'
                              ? 'status-pill status-pill--set'
                              : 'status-pill status-pill--unset';
                        const statusLabel = status === 'deprecated'
                          ? t('env.table.status_deprecated')
                          : status === 'automatic'
                            ? t('env.table.status_automatic')
                            : status === 'set'
                              ? t('env.table.status_set')
                              : t('env.table.status_not_set');
                        return (
                          <span className={statusClass}>
                            {statusLabel}
                          </span>
                        );
                      },
                    },
                    {
                      key: 'value',
                      title: t('env.table.value'),
                      render: (row) =>
                        (row as EnvCatalogItem).value ? (
                          <code className="env-value">{(row as EnvCatalogItem).value}</code>
                        ) : (
                          t('common.na')
                        ),
                    },
                    {
                      key: 'default',
                      title: t('env.table.default_json'),
                      render: (row) => {
                        const item = row as EnvCatalogItem;
                        if (item.is_set) return t('common.na');
                        const defaultValue = item.default_value ?? null;
                        if (!defaultValue) return t('common.na');
                        return <code className="env-default">{defaultValue}</code>;
                      },
                    },
                  ]}
                />
              </div>
            </details>
          </Card>
        );
      })}
    </section>
  );
}
