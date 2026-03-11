import { useEffect, useMemo, useState, type ChangeEvent } from 'react';

import { useAuth } from '../../app/auth';
import { createFolder, deletePaths, downloadFile, listFiles, readFile, renamePath, uploadFile, writeFile } from '../../api/files';
import type { FileListItem } from '../../api/types';
import { useI18n } from '../../i18n';
import { formatDateTime } from '../../utils/datetime/formatDateTime';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Table } from '../ui/Table';

interface Props {
  serverId: string;
}

function parentPath(path: string): string {
  if (path === '/' || path.length < 2) return '/';
  const parts = path.split('/').filter(Boolean);
  parts.pop();
  return `/${parts.join('/')}` || '/';
}

function itemName(path: string): string {
  const parts = path.split('/').filter(Boolean);
  return parts[parts.length - 1] || '';
}

function joinPath(base: string, child: string): string {
  const normalizedChild = child.replace(/^\/+/, '');
  if (!normalizedChild) return base || '/';
  if (!base || base === '/') return `/${normalizedChild}`;
  return `${base.replace(/\/+$/, '')}/${normalizedChild}`;
}

export function FileManager({ serverId }: Props) {
  const { can } = useAuth();
  const { language, timezone, t } = useI18n();
  const canWrite = can('files.write', serverId);

  const [root, setRoot] = useState<string | undefined>(undefined);
  const [path, setPath] = useState('/');
  const [items, setItems] = useState<FileListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionBusy, setActionBusy] = useState('');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorPath, setEditorPath] = useState('');
  const [editorContent, setEditorContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameSource, setRenameSource] = useState('');
  const [renameName, setRenameName] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FileListItem | null>(null);

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  async function refresh(nextPath = path) {
    setLoading(true);
    setError('');
    try {
      const response = await listFiles(serverId, nextPath, root);
      setRoot(response.root);
      setPath(response.path);
      setItems(response.items || []);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.load_failed'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh('/');
  }, [serverId]);

  async function openFile(filePath: string) {
    try {
      const response = await readFile(serverId, filePath, root);
      setEditorPath(response.path);
      setEditorContent(response.content || '');
      setEditorOpen(true);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.open_failed'));
    }
  }

  async function saveFile() {
    if (!canWrite) {
      setError(t('files.error.write_forbidden'));
      return;
    }

    setSaving(true);
    setError('');
    try {
      await writeFile(serverId, editorPath, editorContent, root);
      setEditorOpen(false);
      await refresh(path);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.save_failed'));
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!canWrite) {
      setError(t('files.error.upload_forbidden'));
      event.currentTarget.value = '';
      return;
    }

    setError('');
    try {
      setActionBusy('upload');
      await uploadFile(serverId, path, file, file.name, root);
      await refresh(path);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.upload_failed'));
    } finally {
      setActionBusy('');
      event.currentTarget.value = '';
    }
  }

  async function onCreateFolder() {
    if (!canWrite) return;
    const name = createName.trim().replace(/^\/+/, '');
    if (!name) {
      setError(t('files.error.folder_name_required'));
      return;
    }
    setError('');
    setActionBusy('create');
    try {
      await createFolder(serverId, joinPath(path, name), root);
      setCreateOpen(false);
      setCreateName('');
      await refresh(path);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.create_folder_failed'));
    } finally {
      setActionBusy('');
    }
  }

  function startRename(item: FileListItem) {
    setRenameSource(item.path);
    setRenameName(item.name);
    setRenameOpen(true);
  }

  async function onRename() {
    if (!canWrite) return;
    const nextName = renameName.trim().replace(/^\/+/, '');
    if (!nextName) {
      setError(t('files.error.new_name_required'));
      return;
    }

    const target = joinPath(parentPath(renameSource), nextName);
    setError('');
    setActionBusy('rename');
    try {
      await renamePath(serverId, renameSource, target, root);
      setRenameOpen(false);
      setRenameSource('');
      setRenameName('');
      await refresh(path);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.rename_failed'));
    } finally {
      setActionBusy('');
    }
  }

  function startDelete(item: FileListItem) {
    setDeleteTarget(item);
    setDeleteOpen(true);
  }

  async function onDelete() {
    if (!canWrite || !deleteTarget) return;
    setError('');
    setActionBusy('delete');
    try {
      await deletePaths(serverId, [deleteTarget.path], root);
      setDeleteOpen(false);
      setDeleteTarget(null);
      await refresh(path);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.delete_failed'));
    } finally {
      setActionBusy('');
    }
  }

  async function onDownload(filePath: string) {
    setError('');
    setActionBusy(`download:${filePath}`);
    try {
      const { blob, filename } = await downloadFile(serverId, filePath, root);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename || itemName(filePath) || 'download.bin';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('files.error.download_failed'));
    } finally {
      setActionBusy('');
    }
  }

  const rows = useMemo(() => items, [items]);

  return (
    <div>
      <div className="files-toolbar">
        <Button variant="ghost" onClick={() => refresh(parentPath(path))}>
          {t('files.toolbar.up')}
        </Button>
        <Button variant="ghost" onClick={() => refresh(path)} loading={loading}>
          {t('common.refresh')}
        </Button>
        <label className={`btn btn--secondary file-upload ${canWrite ? '' : 'is-disabled'}`}>
          {t('files.toolbar.upload')}
          <input type="file" onChange={onUpload} disabled={!canWrite} />
        </label>
        <Button variant="secondary" onClick={() => setCreateOpen(true)} disabled={!canWrite}>
          {t('files.toolbar.new_folder')}
        </Button>
        <span className="badge">{path}</span>
        {root && <span className="chip chip--muted">{t('files.toolbar.root', { root })}</span>}
      </div>

      {!canWrite && <p className="hint">{t('files.read_only_hint')}</p>}
      {error && <p className="hint hint--error">{error}</p>}

      <Table
        rows={rows}
        emptyText={loading ? t('common.loading') : t('files.empty_folder')}
        columns={[
          {
            key: 'name',
            title: t('files.table.name'),
            render: (row) => {
              const item = row as FileListItem;
              if (item.is_dir) {
                return (
                  <button className="linkish" onClick={() => refresh(item.path)} type="button">
                    {item.name}/
                  </button>
                );
              }
              return (
                <button className="linkish" onClick={() => openFile(item.path)} type="button">
                  {item.name}
                </button>
              );
            },
          },
          {
            key: 'size',
            title: t('files.table.size'),
            render: (row) => {
              const item = row as FileListItem;
              return item.is_dir ? t('common.na') : `${item.size} B`;
            },
          },
          {
            key: 'mode',
            title: t('files.table.mode'),
            render: (row) => (row as FileListItem).mode,
          },
          {
            key: 'modified',
            title: t('files.table.modified'),
            render: (row) => formatDateTime((row as FileListItem).modified_at * 1000, language, timezone),
          },
          {
            key: 'actions',
            title: t('files.table.actions'),
            render: (row) => {
              const item = row as FileListItem;
              return (
                <div className="row-actions">
                  {item.is_file && (
                    <Button variant="ghost" onClick={() => openFile(item.path)}>
                      {t('files.action.edit')}
                    </Button>
                  )}
                  {item.is_file && (
                    <Button
                      variant="ghost"
                      loading={actionBusy === `download:${item.path}`}
                      onClick={() => onDownload(item.path)}
                    >
                      {t('files.action.download')}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => startRename(item)} disabled={!canWrite}>
                    {t('files.action.rename')}
                  </Button>
                  <Button variant="danger" onClick={() => startDelete(item)} disabled={!canWrite}>
                    {t('files.action.delete')}
                  </Button>
                </div>
              );
            },
          },
        ]}
      />

      <Modal open={editorOpen} title={t('files.modal.edit_title', { path: editorPath })} onClose={() => setEditorOpen(false)}>
        <textarea
          className="editor"
          value={editorContent}
          onChange={(event) => setEditorContent(event.target.value)}
          rows={18}
          readOnly={!canWrite}
        />
        <div className="modal__footer">
          <Button variant="ghost" onClick={() => setEditorOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="primary" onClick={saveFile} loading={saving} disabled={!canWrite}>
            {t('common.save')}
          </Button>
        </div>
      </Modal>

      <Modal open={createOpen} title={t('files.modal.create_folder_title')} onClose={() => setCreateOpen(false)}>
        <label className="form-field">
          {t('files.modal.folder_name')}
          <input
            value={createName}
            onChange={(event) => setCreateName(event.target.value)}
            placeholder={t('files.modal.folder_name_placeholder')}
            autoFocus
          />
        </label>
        <div className="modal__footer">
          <Button variant="ghost" onClick={() => setCreateOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="primary" onClick={onCreateFolder} loading={actionBusy === 'create'} disabled={!canWrite}>
            {t('common.create')}
          </Button>
        </div>
      </Modal>

      <Modal open={renameOpen} title={t('files.modal.rename_title', { name: itemName(renameSource) })} onClose={() => setRenameOpen(false)}>
        <label className="form-field">
          {t('files.modal.new_name')}
          <input value={renameName} onChange={(event) => setRenameName(event.target.value)} autoFocus />
        </label>
        <div className="modal__footer">
          <Button variant="ghost" onClick={() => setRenameOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="primary" onClick={onRename} loading={actionBusy === 'rename'} disabled={!canWrite}>
            {t('files.action.rename')}
          </Button>
        </div>
      </Modal>

      <Modal
        open={deleteOpen}
        title={t('files.modal.delete_title', { name: deleteTarget?.name || '' })}
        onClose={() => {
          setDeleteOpen(false);
          setDeleteTarget(null);
        }}
      >
        <p className="hint">
          {deleteTarget?.is_dir
            ? t('files.modal.delete_folder_warning')
            : t('files.modal.delete_file_warning')}
        </p>
        <div className="modal__footer">
          <Button
            variant="ghost"
            onClick={() => {
              setDeleteOpen(false);
              setDeleteTarget(null);
            }}
          >
            {t('common.cancel')}
          </Button>
          <Button variant="danger" onClick={onDelete} loading={actionBusy === 'delete'} disabled={!canWrite}>
            {t('files.action.delete')}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
