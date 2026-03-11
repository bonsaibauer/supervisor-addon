export interface ProcessInfo {
  name: string;
  group: string;
  start: number;
  stop: number;
  now: number;
  state: number;
  statename: string;
  spawnerr: string;
  exitstatus: number;
  logfile: string;
  stdout_logfile: string;
  stderr_logfile: string;
  pid: number;
  description: string;
}

export interface EnvCatalogItem {
  key: string;
  is_set: boolean;
  deprecated?: boolean;
  status?: 'set' | 'unset' | 'deprecated' | 'automatic';
  value?: string | null;
  default_value?: string | null;
}

export interface ServerDetails {
  server_id: string;
  actions: Record<string, { type: string; program: string }>;
  logs: {
    stdout_program?: string;
    stderr_program?: string;
    [key: string]: string | undefined;
  };
  files: {
    roots?: string[];
    writable?: string[];
    startup_config?: string;
    startup_files?: string[];
    startup_json_loaded?: boolean;
    startup_json_error?: string;
    env_keys?: string[];
    env_catalog?: EnvCatalogItem[];
    [key: string]: unknown;
  };
  runtime_program?: string;
  process_info?: ProcessInfo | null;
  error?: string;
}

export interface ActivityEvent {
  ts: number;
  event: string;
  payload: Record<string, unknown>;
}

export interface FileListItem {
  name: string;
  path: string;
  is_file: boolean;
  is_dir: boolean;
  size: number;
  modified_at: number;
  mode: string;
}

export interface FileListResponse {
  ok: boolean;
  server_id: string;
  root: string;
  path: string;
  items: FileListItem[];
}

export interface FileContentsResponse {
  ok: boolean;
  server_id: string;
  root: string;
  path: string;
  size: number;
  content: string;
}

export interface FileOperationResponse {
  ok: boolean;
  server_id: string;
  root?: string;
  path?: string;
  created?: boolean;
  written?: boolean;
  deleted?: string[];
  renamed?: Array<{ from: string; to: string }>;
  count?: number;
}

export interface AuthUser {
  username: string;
  role: string;
  permissions: string[];
  allowed_servers: string[];
  token_kind: string;
  must_change_password: boolean;
  language: string;
  timezone: string;
}

export interface LoginResponse {
  ok: boolean;
  token: string;
  token_type: 'bearer';
  expires_in: number;
  user: AuthUser;
}

export interface MeResponse {
  ok: boolean;
  user: AuthUser;
}

export interface UpdateStatusResponse {
  ok: boolean;
  current_version: string;
  latest_version: string | null;
  latest_tag: string | null;
  update_available: boolean;
  release_url: string;
  update_kind?: string;
  required_action?: string;
  primary_button?: string;
  reason?: string | null;
  recommended_steps?: string[];
  error: string | null;
}

export interface InstallUpdateResponse {
  ok: boolean;
  tag: string | null;
  version: string | null;
  checksum: string | null;
  backup_path: string | null;
  release_url: string | null;
  restart_scheduled: boolean;
  steps: string[];
  error: string | null;
}

export interface RuntimeStatsAvailable {
  available: true;
  cpu_percent: number;
  cpu_cores_total: number;
  cpu_cores_percent: number[];
  cpu_used_cores: number;
  memory_used_bytes: number;
  memory_limit_bytes: number;
  memory_percent: number;
}

export interface RuntimeStatsUnavailable {
  available: false;
  error: string;
}

export type RuntimeStats = RuntimeStatsAvailable | RuntimeStatsUnavailable;

export type NewsLevel = 'info' | 'warning' | 'error' | 'update';
export type NewsI18nValues = Record<string, string | number | boolean | null>;

export interface NewsAction {
  id: string;
  label: string;
  label_values?: NewsI18nValues;
  kind: 'navigate' | 'external' | 'install_update' | 'refresh_news' | 'renew_tls_cert';
  target?: string | null;
}

export interface NewsItem {
  id: string;
  level: NewsLevel;
  title: string;
  title_values?: NewsI18nValues;
  message: string;
  message_values?: NewsI18nValues;
  category: string;
  created_at: number;
  actions: NewsAction[];
  is_read?: boolean;
}
