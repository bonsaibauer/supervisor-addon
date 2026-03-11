import { downloadFile, listFiles } from './files';
import { createBackup, getServer } from './servers';
import type { FileListItem } from './types';

type BackupPreflight = {
  ok: boolean;
  message: string;
};

function envCatalogMap(rawCatalog: unknown): Record<string, { isSet: boolean; value: string | null }> {
  const map: Record<string, { isSet: boolean; value: string | null }> = {};
  if (!Array.isArray(rawCatalog)) return map;

  for (const item of rawCatalog) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const record = item as Record<string, unknown>;
    const key = typeof record.key === 'string' ? record.key.trim() : '';
    if (!key) continue;
    map[key] = {
      isSet: Boolean(record.is_set),
      value: record.value == null ? null : String(record.value),
    };
  }
  return map;
}

export async function checkBackupPreconditions(serverId: string): Promise<BackupPreflight> {
  const server = await getServer(serverId);
  const rawFiles = (server.files || {}) as Record<string, unknown>;
  const envMap = envCatalogMap(rawFiles.env_catalog);

  const backupCron = envMap.BACKUP_CRON;
  if (!backupCron?.isSet) {
    return {
      ok: false,
      message: 'backups.preflight.backup_cron_missing',
    };
  }

  return { ok: true, message: '' };
}

export async function triggerBackup(serverId: string) {
  const check = await checkBackupPreconditions(serverId);
  if (!check.ok) {
    throw new Error(check.message);
  }
  return createBackup(serverId);
}

function resolveBackupLocation(backupDir: string | null, roots: string[]): { root?: string; path: string } {
  if (!backupDir) {
    return { path: '/server/backups' };
  }

  const normalizedBackup = backupDir.replace(/\\/g, '/').replace(/\/+$/, '');
  for (const root of roots) {
    const normalizedRoot = String(root).replace(/\\/g, '/').replace(/\/+$/, '');
    if (!normalizedRoot) continue;
    if (normalizedBackup === normalizedRoot) {
      return { root, path: '/' };
    }
    if (normalizedBackup.startsWith(`${normalizedRoot}/`)) {
      const relative = normalizedBackup.slice(normalizedRoot.length).replace(/^\/+/, '');
      return { root, path: relative ? `/${relative}` : '/' };
    }
  }

  return { path: normalizedBackup.startsWith('/') ? normalizedBackup : `/${normalizedBackup}` };
}

export async function listBackupFiles(
  serverId: string
): Promise<{ root: string; path: string; items: FileListItem[] }> {
  const server = await getServer(serverId);
  const rawFiles = (server.files || {}) as Record<string, unknown>;
  const backupDir = typeof rawFiles.backup_dir === 'string' && rawFiles.backup_dir.trim()
    ? rawFiles.backup_dir.trim()
    : null;
  const roots = Array.isArray(rawFiles.roots)
    ? rawFiles.roots.filter((item) => typeof item === 'string' && String(item).trim()) as string[]
    : [];

  const location = resolveBackupLocation(backupDir, roots);
  const response = await listFiles(serverId, location.path, location.root);
  const files = (response.items || [])
    .filter((item) => item.is_file)
    .sort((a, b) => Number(b.modified_at) - Number(a.modified_at));

  return {
    root: response.root,
    path: response.path,
    items: files,
  };
}

export async function downloadBackupFile(serverId: string, path: string, root?: string) {
  return downloadFile(serverId, path, root);
}
