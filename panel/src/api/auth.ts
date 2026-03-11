import { apiRequest } from './client';
import type { LoginResponse, MeResponse } from './types';

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: { username, password },
  });
}

export async function me(): Promise<MeResponse> {
  return apiRequest<MeResponse>('/auth/me', { method: 'GET' });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/change-password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

export async function logout(): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>('/auth/logout', {
    method: 'POST',
  });
}

export async function updatePreferences(preferences: {
  language?: string;
  timezone?: string;
}): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/preferences', {
    method: 'PATCH',
    body: preferences,
  });
}
