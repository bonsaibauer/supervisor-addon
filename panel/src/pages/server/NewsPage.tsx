import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { getServerNews, installLatestUpdate, renewServerTlsCertificate, setServerNewsRead } from '../../api/servers';
import type { NewsAction, NewsI18nValues, NewsItem } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { useI18n } from '../../i18n';

type NewsFilter = 'unread' | 'read' | 'all';

function levelBadgeClass(level: string): string {
  if (level === 'error') return 'status-pill status-pill--danger';
  if (level === 'warning') return 'status-pill status-pill--warn';
  if (level === 'update') return 'status-pill status-pill--update';
  return 'status-pill status-pill--neutral';
}

export function NewsPage() {
  const serverId = DEFAULT_SERVER_ID;
  const navigate = useNavigate();
  const { t } = useI18n();
  const { can } = useAuth();
  const canRead = can('news.read', serverId);
  const canAdmin = can('admin', serverId);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [renewingTls, setRenewingTls] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busyId, setBusyId] = useState('');
  const [filter, setFilter] = useState<NewsFilter>('unread');

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  const resolveNewsValues = (values?: NewsI18nValues): Record<string, string | number | boolean | null | undefined> | undefined => {
    if (!values) return undefined;
    const next: Record<string, string | number | boolean | null | undefined> = {};
    for (const [key, raw] of Object.entries(values)) {
      if (typeof raw === 'string') {
        const translated = t(raw);
        next[key] = translated || raw;
      } else {
        next[key] = raw;
      }
    }
    return next;
  };

  const localizeNewsText = (key: string, values?: NewsI18nValues): string => t(key, resolveNewsValues(values));

  const localizeNewsLevel = (level: string): string => t(`news.level.${level}`);

  const localizeNewsCategory = (category: string): string => t(`news.category.${category}`);

  const actionPriority = (action: NewsAction): number => {
    if (action.id === 'open.env') return 0;
    return 1;
  };

  async function load(refresh = false) {
    if (!canRead) {
      setError(t('news.page.error.permissions'));
      return;
    }
    setLoading(true);
    setError('');
    setMessage('');
    try {
      let next = await getServerNews(serverId, refresh, true);
      if (refresh) {
        const updateItem = next.find((item) => item.category === 'update');
        if (updateItem && updateItem.is_read) {
          try {
            await setServerNewsRead(serverId, updateItem.id, false);
          } catch {
            // Keep local feedback even if read-state persistence fails.
          }
          next = next.map((item) => (item.id === updateItem.id ? { ...item, is_read: false } : item));
        }
      }
      setItems(next || []);
      if (refresh) setMessage(t('topnav.news.update_status_checked'));
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('news.page.error.load_failed'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 60000);
    return () => {
      window.clearInterval(timer);
    };
  }, [serverId, canRead]);

  async function toggleRead(item: NewsItem, read: boolean) {
    if (!item.id) return;
    setBusyId(item.id);
    setError('');
    try {
      await setServerNewsRead(serverId, item.id, read);
      setItems((previous) => previous.map((entry) => (entry.id === item.id ? { ...entry, is_read: read } : entry)));
      const refreshed = await getServerNews(serverId, false, true);
      setItems(refreshed || []);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('news.page.error.update_state_failed'));
    } finally {
      setBusyId('');
    }
  }

  async function onInstallUpdate() {
    if (!canAdmin || installing) return;
    if (!window.confirm(t('topnav.news.install_confirm'))) return;
    setInstalling(true);
    setError('');
    setMessage('');
    try {
      const result = await installLatestUpdate(true);
      if (!result.ok) {
        setError(result.error ? localizeErrorMessage(result.error) : t('topnav.news.install_failed'));
        return;
      }
      setMessage(result.restart_scheduled ? t('topnav.news.installed_restart_scheduled') : t('topnav.news.installed'));
      await load(true);
    } catch (err) {
      setError(err instanceof Error ? localizeErrorMessage(err.message) : t('topnav.news.install_failed'));
    } finally {
      setInstalling(false);
    }
  }

  async function runNewsAction(action: NewsAction) {
    if (action.kind === 'navigate') {
      navigate(action.target || '/');
      return;
    }
    if (action.kind === 'external') {
      if (action.target) window.open(action.target, '_blank', 'noopener,noreferrer');
      return;
    }
    if (action.kind === 'install_update') {
      await onInstallUpdate();
      return;
    }
    if (action.kind === 'renew_tls_cert') {
      if (!canAdmin || renewingTls) return;
      if (!window.confirm(t('topnav.news.tls_confirm'))) return;
      setRenewingTls(true);
      try {
        const result = await renewServerTlsCertificate(serverId);
        const days = typeof result.expires_in_days === 'number' ? result.expires_in_days : null;
        setMessage(days === null || days < 0 ? t('topnav.news.tls_renewed') : t('topnav.news.tls_renewed_days', { days }));
        await load(true);
      } finally {
        setRenewingTls(false);
      }
      return;
    }
    if (action.kind === 'refresh_news') {
      setCheckingUpdate(true);
      try {
        await load(true);
      } finally {
        setCheckingUpdate(false);
      }
    }
  }

  const filtered = useMemo(() => {
    const base =
      filter === 'all'
        ? items
        : filter === 'read'
          ? items.filter((item) => Boolean(item.is_read))
          : items.filter((item) => !item.is_read);
    return [...base].sort((a, b) => {
      const aUpdate = a.level === 'update' ? 1 : 0;
      const bUpdate = b.level === 'update' ? 1 : 0;
      return bUpdate - aUpdate;
    });
  }, [items, filter]);

  const unreadCount = useMemo(() => items.filter((item) => !item.is_read).length, [items]);
  const readCount = useMemo(() => items.filter((item) => Boolean(item.is_read)).length, [items]);

  return (
    <section className="page">
      <Card
        title={t('news.page.title')}
        subtitle={t('news.page.subtitle', { server_id: serverId })}
        actions={
          <div className="row-actions">
            <Button variant="secondary" onClick={() => void runNewsAction({ id: 'check-update', label: 'topnav.news.check_update_button', kind: 'refresh_news' })} loading={checkingUpdate}>
              {t('topnav.news.check_update_button')}
            </Button>
            <Button variant="ghost" onClick={() => void load(false)} loading={loading}>
              {t('topnav.news.refresh_button')}
            </Button>
          </div>
        }
      >
        <div className="segmented">
          <button type="button" className={filter === 'unread' ? 'is-active' : ''} onClick={() => setFilter('unread')}>
            {t('news.page.filter.unread', { count: unreadCount })}
          </button>
          <button type="button" className={filter === 'read' ? 'is-active' : ''} onClick={() => setFilter('read')}>
            {t('news.page.filter.read', { count: readCount })}
          </button>
          <button type="button" className={filter === 'all' ? 'is-active' : ''} onClick={() => setFilter('all')}>
            {t('news.page.filter.all', { count: items.length })}
          </button>
        </div>
        {error && <p className="hint hint--error">{error}</p>}

        <div className="news-manage-list">
          {filtered.length === 0 && (
            <p className="hint">{loading ? t('news.page.loading') : filter === 'unread' ? t('news.page.empty.unread') : t('news.page.empty.filter')}</p>
          )}
          {filtered.map((item) => (
            <article
              key={item.id}
              className={`news-feed__item news-feed__item--${item.level}${item.id === 'support.reminder' ? ' news-feed__item--support' : ''}`}
            >
              <header className="news-feed__header">
                <h4>{localizeNewsText(item.title, item.title_values)}</h4>
                <span className={levelBadgeClass(item.level)}>{localizeNewsLevel(item.level)}</span>
              </header>
              <p className="runtime-line">{localizeNewsText(item.message, item.message_values)}</p>
              <p className="runtime-line runtime-line--muted">{t('topnav.news.category', { category: localizeNewsCategory(item.category) })}</p>
              <p className="runtime-line runtime-line--muted">
                {t('news.page.status', { status: item.is_read ? t('news.page.status.read') : t('news.page.status.unread') })}
              </p>
              <div className="news-feed__footer">
                <div className="news-feed__actions-left">
                  {[...item.actions].sort((a, b) => actionPriority(a) - actionPriority(b)).map((action) => (
                    <button
                      key={`${item.id}-${action.id}`}
                      type="button"
                      className="btn btn--secondary"
                      onClick={() => void runNewsAction(action)}
                      disabled={loading || checkingUpdate || installing || renewingTls}
                    >
                      {action.kind === 'install_update' && installing
                        ? t('news.page.installing')
                        : action.kind === 'renew_tls_cert' && renewingTls
                          ? t('topnav.news.renewing')
                          : localizeNewsText(action.label, action.label_values)}
                    </button>
                  ))}
                </div>
                <div className="news-feed__actions-right">
                  {!item.is_read ? (
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={busyId === item.id}
                      onClick={() => void toggleRead(item, true)}
                    >
                      {busyId === item.id ? t('topnav.news.saving') : t('news.page.mark_read')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={busyId === item.id}
                      onClick={() => void toggleRead(item, false)}
                    >
                      {busyId === item.id ? t('topnav.news.saving') : t('news.page.mark_unread')}
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
        {message && <p className="hint">{message}</p>}
      </Card>
    </section>
  );
}
