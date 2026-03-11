import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { readFile, writeFile } from '../../api/files';
import { getServer } from '../../api/servers';
import type { ServerDetails } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { useI18n } from '../../i18n';

const DEFAULT_CONFIG_PATH = '/server/enshrouded_server.json';

function serverRoots(server: ServerDetails | null): string[] {
  if (!server) return [];
  const raw = server.files as Record<string, unknown>;
  if (!Array.isArray(raw.roots)) return [];
  return raw.roots
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => item.trim());
}

function resolveFileLocation(path: string, roots: string[], selectedRoot?: string): { root?: string; path: string } {
  const normalizedInput = path.trim().replace(/\\/g, '/');
  const normalizedRoots = roots.map((root) => root.trim().replace(/\\/g, '/').replace(/\/+$/, ''));

  for (let index = 0; index < roots.length; index += 1) {
    const root = roots[index];
    const normalizedRoot = normalizedRoots[index];
    if (!normalizedRoot) continue;
    if (normalizedInput === normalizedRoot) {
      return { root, path: '/' };
    }
    if (normalizedInput.startsWith(`${normalizedRoot}/`)) {
      const relative = normalizedInput.slice(normalizedRoot.length).replace(/^\/+/, '');
      return { root, path: relative ? `/${relative}` : '/' };
    }
  }

  if (normalizedInput.startsWith('/')) {
    return { root: selectedRoot, path: normalizedInput };
  }
  return { root: selectedRoot, path: `/${normalizedInput}` };
}

function configCandidates(server: ServerDetails | null): string[] {
  if (!server) return [DEFAULT_CONFIG_PATH];
  const raw = server.files as Record<string, unknown>;
  const configured: string[] = [];

  const startupConfig = raw.startup_config;
  if (typeof startupConfig === 'string' && startupConfig.trim()) {
    configured.push(startupConfig.trim());
  }

  const startupFiles = raw.startup_files;
  if (Array.isArray(startupFiles)) {
    startupFiles.forEach((item) => {
      if (typeof item === 'string' && item.trim()) {
        configured.push(item.trim());
      }
    });
  }

  const values = [...new Set(configured)];
  return values.length > 0 ? values : [DEFAULT_CONFIG_PATH];
}

export function ConfigPage() {
  const serverId = DEFAULT_SERVER_ID;
  const { can } = useAuth();
  const { t } = useI18n();
  const canReadFiles = can('files.read', serverId);
  const canWriteFiles = can('files.write', serverId);

  const [server, setServer] = useState<ServerDetails | null>(null);
  const [configPath, setConfigPath] = useState('');
  const [configRoot, setConfigRoot] = useState<string | undefined>(undefined);
  const [configContent, setConfigContent] = useState('');
  const [configMessage, setConfigMessage] = useState('');
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const editorRef = useRef<HTMLTextAreaElement | null>(null);

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  const rootSuffix = (value?: string): string => (value ? t('common.root_suffix', { root: value }) : '');

  const candidates = useMemo(() => configCandidates(server), [server]);

  useEffect(() => {
    if (!serverId) return;
    void getServer(serverId).then((value) => {
      setServer(value);
      setConfigPath((prev) => prev || configCandidates(value)[0] || DEFAULT_CONFIG_PATH);
    }).catch(() => {
      setServer(null);
      setConfigPath((prev) => prev || DEFAULT_CONFIG_PATH);
    });
  }, [serverId]);

  async function loadConfig(path = configPath) {
    if (!canReadFiles) {
      setConfigMessage(t('config.page.error.read_forbidden'));
      return;
    }
    const normalized = path.trim();
    if (!normalized) {
      setConfigMessage(t('config.page.error.path_required'));
      return;
    }

    setConfigLoading(true);
    setConfigMessage('');
    try {
      const location = resolveFileLocation(normalized, serverRoots(server), configRoot);
      const response = await readFile(serverId, location.path, location.root);
      setConfigPath(response.path);
      setConfigRoot(response.root);
      setConfigContent(response.content || '');
      setConfigMessage(t('config.page.loaded', { path: response.path, root_suffix: rootSuffix(response.root) }));
    } catch (error) {
      setConfigMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('config.page.error.load_failed'));
    } finally {
      setConfigLoading(false);
    }
  }

  async function saveConfig() {
    if (!canWriteFiles) {
      setConfigMessage(t('config.page.error.write_forbidden'));
      return;
    }
    const normalized = configPath.trim();
    if (!normalized) {
      setConfigMessage(t('config.page.error.path_required'));
      return;
    }

    setConfigSaving(true);
    setConfigMessage('');
    try {
      const location = resolveFileLocation(normalized, serverRoots(server), configRoot);
      await writeFile(serverId, location.path, configContent, location.root);
      setConfigPath(location.path);
      setConfigRoot(location.root);
      setConfigMessage(t('config.page.saved', { path: location.path, root_suffix: rootSuffix(location.root) }));
    } catch (error) {
      setConfigMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('config.page.error.save_failed'));
    } finally {
      setConfigSaving(false);
    }
  }

  useLayoutEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.style.height = 'auto';
    editor.style.height = `${Math.max(editor.scrollHeight, 300)}px`;
  }, [configContent]);

  return (
    <section className="page">
      <Card title={t('config.page.title')} subtitle={t('config.page.subtitle')}>
        {!canReadFiles && <p className="hint">{t('config.page.read_access_required')}</p>}
        <div className="config-editor-toolbar">
          <label className="form-field">
            {t('config.page.suggested_files')}
            <select
              value={configPath}
              onChange={(event) => setConfigPath(event.target.value)}
              disabled={!canReadFiles}
            >
              {candidates.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            {t('config.page.custom_path')}
            <input
              value={configPath}
              onChange={(event) => setConfigPath(event.target.value)}
              placeholder={DEFAULT_CONFIG_PATH}
              disabled={!canReadFiles}
            />
          </label>
        </div>
        <div className="row-actions">
          <Button variant="secondary" loading={configLoading} onClick={() => loadConfig()} disabled={!canReadFiles}>
            {t('config.page.button.load')}
          </Button>
          <Button variant="primary" loading={configSaving} onClick={saveConfig} disabled={!canWriteFiles}>
            {t('config.page.button.save')}
          </Button>
        </div>
        <textarea
          ref={editorRef}
          className="editor config-editor"
          value={configContent}
          onChange={(event) => setConfigContent(event.target.value)}
          readOnly={!canWriteFiles}
          rows={1}
        />
        {configMessage && <p className="hint">{configMessage}</p>}
      </Card>

    </section>
  );
}

