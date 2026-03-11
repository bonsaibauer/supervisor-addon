const envDefaultServerId =
  typeof import.meta.env.VITE_DEFAULT_SERVER_ID === 'string' ? import.meta.env.VITE_DEFAULT_SERVER_ID.trim() : '';

export const DEFAULT_SERVER_ID = envDefaultServerId || 'enshrouded';
