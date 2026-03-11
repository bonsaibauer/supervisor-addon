import { apiDownload, apiRequest } from './client';
import type { FileContentsResponse, FileListResponse, FileOperationResponse } from './types';

export async function listFiles(serverId: string, path = '/', root?: string): Promise<FileListResponse> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/list`, {
    method: 'GET',
    query: { path, root },
  });
}

export async function readFile(serverId: string, path: string, root?: string): Promise<FileContentsResponse> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/contents`, {
    method: 'GET',
    query: { path, root },
  });
}

export async function writeFile(serverId: string, path: string, content: string, root?: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/write`, {
    method: 'POST',
    body: { path, content, root },
  });
}

export async function createFolder(serverId: string, path: string, root?: string): Promise<FileOperationResponse> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/create-folder`, {
    method: 'POST',
    body: { path, root },
  });
}

export async function renamePath(
  serverId: string,
  source: string,
  target: string,
  root?: string
): Promise<FileOperationResponse> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/rename`, {
    method: 'POST',
    body: { items: [{ source, target }], root },
  });
}

export async function deletePaths(serverId: string, paths: string[], root?: string): Promise<FileOperationResponse> {
  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/delete`, {
    method: 'POST',
    body: { paths, root },
  });
}

export async function uploadFile(
  serverId: string,
  directory: string,
  file: Blob,
  filename?: string,
  root?: string
): Promise<{ ok: boolean }> {
  const form = new FormData();
  form.append('upload', file, filename || 'upload.bin');
  form.append('directory', directory || '/');
  if (root) {
    form.append('root', root);
  }

  return apiRequest(`/api/servers/${encodeURIComponent(serverId)}/files/upload`, {
    method: 'POST',
    bodyType: 'form-data',
    body: form,
  });
}

export async function downloadFile(serverId: string, path: string, root?: string): Promise<{ blob: Blob; filename: string | null }> {
  return apiDownload(`/api/servers/${encodeURIComponent(serverId)}/files/download`, {
    query: { path, root },
  });
}
