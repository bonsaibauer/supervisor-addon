import { apiRequest, buildApiUrl } from './client';
import type { ActivityEvent, InstallUpdateResponse, NewsItem, RuntimeStats, ServerDetails, UpdateStatusResponse } from './types';

export async function getServer(serverId: string): Promise<ServerDetails> {
  const response = await apiRequest<{ ok: boolean; item: ServerDetails }>(`/api/servers/${encodeURIComponent(serverId)}`);
  return response.item;
}

export async function sendPowerSignal(
  serverId: string,
  signal: 'start' | 'stop' | 'restart' | 'restart_safe'
): Promise<{ ok: boolean; signal: string }> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/power`, {
    method: 'POST',
    body: { signal, wait: false },
  });
}

export async function createBackup(serverId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/backups`, {
    method: 'POST',
    body: { wait: false },
  });
}

export async function runUpdate(serverId: string, mode: 'run' | 'force'): Promise<{ ok: boolean }> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/updates`, {
    method: 'POST',
    body: { mode, wait: false },
  });
}

export async function serverActivity(serverId: string, limit = 100): Promise<{ ok: boolean; items: ActivityEvent[] }> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/activity`, {
    method: 'GET',
    query: { limit },
  });
}

export function streamLogUrl(serverId: string, channel: 'supervisor' | 'enshrouded', offset: number): string {
  return buildApiUrl(`/api/servers/${encodeURIComponent(serverId)}/logs/${channel}/stream`, {
    offset,
    chunk_bytes: 8192,
  });
}

export async function getUpdateStatus(refresh = false): Promise<UpdateStatusResponse> {
  return apiRequest<UpdateStatusResponse>('/api/update/status', {
    method: 'GET',
    query: refresh ? { refresh: true } : undefined,
  });
}

export async function getServerStats(serverId: string): Promise<RuntimeStats> {
  const response = await apiRequest<{ ok: boolean; item: RuntimeStats }>(
    `/api/servers/${encodeURIComponent(serverId)}/stats`,
    { method: 'GET' }
  );
  return response.item;
}

export async function installLatestUpdate(restart = true): Promise<InstallUpdateResponse> {
  return apiRequest<InstallUpdateResponse>('/api/update/install', {
    method: 'POST',
    body: { restart },
  });
}

export async function getServerNews(serverId: string, refresh = false, includeRead = true): Promise<NewsItem[]> {
  const response = await apiRequest<{ ok: boolean; server_id: string; items: NewsItem[] }>(
    `/api/servers/${encodeURIComponent(serverId)}/news`,
    {
      method: 'GET',
      query: {
        ...(refresh ? { refresh: true } : {}),
        include_read: includeRead,
      },
    }
  );
  return Array.isArray(response.items) ? response.items : [];
}

export async function setServerNewsRead(serverId: string, newsId: string, read: boolean): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(
    `/api/servers/${encodeURIComponent(serverId)}/news/${encodeURIComponent(newsId)}/read`,
    {
      method: 'POST',
      body: { read },
    }
  );
}

export async function renewServerTlsCertificate(serverId: string): Promise<{ ok: boolean; expires_in_days?: number }> {
  return apiRequest<{ ok: boolean; expires_in_days?: number }>(
    `/api/servers/${encodeURIComponent(serverId)}/tls/renew`,
    {
      method: 'POST',
    }
  );
}
