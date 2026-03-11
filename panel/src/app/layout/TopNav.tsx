import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { getServerNews, installLatestUpdate, renewServerTlsCertificate, setServerNewsRead } from '../../api/servers';
import type { NewsAction, NewsI18nValues, NewsItem } from '../../api/types';
import { LanguageSwitcher } from '../../components/i18n/LanguageSwitcher';
import { Modal } from '../../components/ui/Modal';
import { useI18n } from '../../i18n';
import { useAuth } from '../auth';
import { DEFAULT_SERVER_ID } from '../defaultServer';

export function TopNav() {
  const { t } = useI18n();
  const { user, logout, can } = useAuth();
  const canUseNews = can('news.read', DEFAULT_SERVER_ID);
  const navigate = useNavigate();
  const repositoryUrl = 'https://github.com/bonsaibauer/supervisor-addon';
  const issuesUrl = 'https://github.com/bonsaibauer/supervisor-addon/issues/new/choose';
  const buyMeCoffeeUrl = 'https://buymeacoffee.com/bonsaibauer';
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [loadingNews, setLoadingNews] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [renewingTls, setRenewingTls] = useState(false);
  const [installMessage, setInstallMessage] = useState('');
  const [newsMessage, setNewsMessage] = useState('');
  const [newsOpen, setNewsOpen] = useState(false);
  const [busyNewsId, setBusyNewsId] = useState('');

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

  const localizeNewsCategory = (category: string): string => t(`news.category.${category}`);

  const localizeNewsLevel = (level: string): string => t(`news.level.${level}`);

  async function refreshNews(showFeedback = false, forceUpdateRefresh = false) {
    if (!canUseNews) return;
    setLoadingNews(true);
    if (showFeedback) {
      setNewsMessage(forceUpdateRefresh ? t('topnav.news.checking_update_status') : t('topnav.news.refreshing_feed'));
    }
    try {
      let items = await getServerNews(DEFAULT_SERVER_ID, forceUpdateRefresh, true);
      if (forceUpdateRefresh) {
        const updateItem = items.find((item) => item.category === 'update');
        if (updateItem && updateItem.is_read) {
          try {
            await setServerNewsRead(DEFAULT_SERVER_ID, updateItem.id, false);
          } catch {
            // Keep UI feedback even if read-state persistence fails.
          }
          items = items.map((item) => (item.id === updateItem.id ? { ...item, is_read: false } : item));
        }
      }
      setNewsItems(items);
      if (showFeedback) setNewsMessage(forceUpdateRefresh ? t('topnav.news.update_status_checked') : t('topnav.news.feed_updated'));
    } catch (error) {
      if (showFeedback) setNewsMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('topnav.news.load_failed'));
    } finally {
      setLoadingNews(false);
    }
  }

  useEffect(() => {
    if (!canUseNews) {
      setNewsItems([]);
      setNewsOpen(false);
      return;
    }
    void refreshNews();
    const timer = window.setInterval(() => {
      void refreshNews();
    }, 60000);
    return () => {
      window.clearInterval(timer);
    };
  }, [canUseNews]);

  async function onInstallUpdate() {
    if (!can('admin') || installing) return;
    if (!window.confirm(t('topnav.news.install_confirm'))) return;
    setInstalling(true);
    setInstallMessage('');
    try {
      const result = await installLatestUpdate(true);
      if (!result.ok) {
        setInstallMessage(result.error ? localizeErrorMessage(result.error) : t('topnav.news.install_failed'));
        return;
      }
      setInstallMessage(result.restart_scheduled ? t('topnav.news.installed_restart_scheduled') : t('topnav.news.installed'));
      await refreshNews(true);
    } catch (error) {
      setInstallMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('topnav.news.install_failed'));
    } finally {
      setInstalling(false);
    }
  }

  async function runNewsAction(action: NewsAction) {
    if (action.kind === 'navigate') {
      setNewsOpen(false);
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
      if (!can('admin') || renewingTls) return;
      if (!window.confirm(t('topnav.news.tls_confirm'))) return;
      setRenewingTls(true);
      setNewsMessage('');
      try {
        const result = await renewServerTlsCertificate(DEFAULT_SERVER_ID);
        const days = typeof result.expires_in_days === 'number' ? result.expires_in_days : null;
        setNewsMessage(
          days === null || days < 0 ? t('topnav.news.tls_renewed') : t('topnav.news.tls_renewed_days', { days })
        );
        await refreshNews(true);
      } catch (error) {
        setNewsMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('topnav.news.tls_failed'));
      } finally {
        setRenewingTls(false);
      }
      return;
    }
    if (action.kind === 'refresh_news') {
      await refreshNews(true);
    }
  }

  async function markNewsRead(newsId: string) {
    if (!newsId) return;
    setBusyNewsId(newsId);
    try {
      await setServerNewsRead(DEFAULT_SERVER_ID, newsId, true);
      setNewsItems((previous) => previous.map((item) => (item.id === newsId ? { ...item, is_read: true } : item)));
    } catch (error) {
      setNewsMessage(error instanceof Error ? localizeErrorMessage(error.message) : t('topnav.news.update_read_state_failed'));
    } finally {
      setBusyNewsId('');
    }
  }

  const unreadItems = newsItems.filter((item) => !item.is_read);
  const actionPriority = (action: NewsAction): number => {
    if (action.id === 'open.env') return 0;
    return 1;
  };
  const newsPriority = (item: NewsItem): number => {
    if (item.level === 'update') return 0;
    if (item.level === 'error') return 1;
    if (item.level === 'warning') return 2;
    return 3; // info + default
  };
  const sortedUnreadItems = [...unreadItems].sort((a, b) => {
    const bucketDiff = newsPriority(a) - newsPriority(b);
    if (bucketDiff !== 0) return bucketDiff;

    const aSupport = a.id === 'support.reminder' ? 1 : 0;
    const bSupport = b.id === 'support.reminder' ? 1 : 0;
    if (a.level === 'info' && b.level === 'info' && aSupport !== bSupport) {
      return bSupport - aSupport;
    }

    return 0;
  });
  const alertCount = unreadItems.filter((item) => item.level === 'warning' || item.level === 'error').length;

  return (
    <header className="topnav">
      <div className="topnav__inner">
        <Link to="/" className="brand">
          <span className="brand__dot" />
          <span>{t('topnav.brand')}</span>
        </Link>

        <div className="topnav__meta">
          <a className="chip chip--link chip--github" href={repositoryUrl} target="_blank" rel="noreferrer">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
              <path
                fill="currentColor"
                d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.48 7.48 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z"
              />
            </svg>
            <span>{t('topnav.github')}</span>
          </a>
          {installMessage && <span className="chip chip--muted">{installMessage}</span>}
          <a className="chip chip--issue" href={issuesUrl} target="_blank" rel="noreferrer">
            <span aria-hidden="true">🚨</span>
            <span>{t('topnav.report_issue')}</span>
          </a>
          <a
            className="chip chip--coffee"
            href={buyMeCoffeeUrl}
            target="_blank"
            rel="noreferrer"
            aria-label="Buy me a coffee"
            title="Buy me a coffee"
          >
            <span className="chip__mark chip__mark--coffee" aria-hidden="true">☕</span>
            <span>{t('topnav.support')}</span>
            <span className="chip__spark" aria-hidden="true" />
          </a>
          {canUseNews && (
            <button
              type="button"
              className={`chip chip--chirper-news${alertCount > 0 ? ' chip--pulse' : ''}`}
              onClick={() => setNewsOpen(true)}
            >
                <span className="chip__mark" aria-hidden="true">
                  🐦
                </span>
                <span>{t('topnav.chirper')}</span>
                {unreadItems.length > 0 ? <span className="chip__notif chip__notif--count">{unreadItems.length}</span> : <span className="chip__notif" aria-hidden="true" />}
            </button>
          )}
          {user && <span className="chip">{user.username}</span>}
          {user && (
            <LanguageSwitcher />
          )}
          {user && (
            <button
              className="btn btn--ghost"
              onClick={async () => {
                await logout();
                navigate('/login', { replace: true });
              }}
              type="button"
            >
              {t('topnav.logout')}
            </button>
          )}
        </div>
      </div>
      <Modal open={canUseNews && newsOpen} title={t('topnav.news.title')} onClose={() => setNewsOpen(false)}>
        <div className="update-news">
          <div className="modal__footer update-news__footer">
            <button className="btn btn--secondary" onClick={() => void refreshNews(true)} type="button" disabled={loadingNews}>
              {loadingNews ? t('topnav.news.refreshing_button') : t('topnav.news.refresh_button')}
            </button>
            <button className="btn btn--secondary" onClick={() => void refreshNews(true, true)} type="button" disabled={loadingNews}>
              {loadingNews ? t('topnav.news.checking_button') : t('topnav.news.check_update_button')}
            </button>
            <button className="btn btn--ghost" onClick={() => { setNewsOpen(false); navigate('/news'); }} type="button">
              {t('topnav.news.open_news_tab')}
            </button>
          </div>
          {unreadItems.length === 0 ? (
            <p className="hint">{t('topnav.news.no_unread')}</p>
          ) : (
            <div className="news-feed news-feed--scroll">
              {sortedUnreadItems.map((item) => (
                <article
                  key={item.id}
                  className={`news-feed__item news-feed__item--${item.level}${item.id === 'support.reminder' ? ' news-feed__item--support' : ''}`}
                >
                  <header className="news-feed__header">
                    <h4>{localizeNewsText(item.title, item.title_values)}</h4>
                    <span className={`status-pill status-pill--${item.level === 'error' ? 'danger' : item.level === 'warning' ? 'warn' : item.level === 'update' ? 'update' : 'neutral'}`}>
                      {localizeNewsLevel(item.level)}
                    </span>
                  </header>
                  <p className="runtime-line">{localizeNewsText(item.message, item.message_values)}</p>
                  <p className="runtime-line runtime-line--muted">{t('topnav.news.category', { category: localizeNewsCategory(item.category) })}</p>
                  <div className="news-feed__footer">
                    <div className="news-feed__actions-left">
                      {[...item.actions].sort((a, b) => actionPriority(a) - actionPriority(b)).map((action) => (
                        <button
                          key={`${item.id}-${action.id}`}
                          type="button"
                          className="btn btn--secondary"
                          onClick={() => void runNewsAction(action)}
                          disabled={installing || renewingTls || loadingNews}
                        >
                          {action.kind === 'renew_tls_cert' && renewingTls ? t('topnav.news.renewing') : localizeNewsText(action.label, action.label_values)}
                        </button>
                      ))}
                    </div>
                    <div className="news-feed__actions-right">
                      <button
                        type="button"
                        className="btn btn--ghost"
                        onClick={() => void markNewsRead(item.id)}
                        disabled={busyNewsId === item.id || loadingNews}
                      >
                        {busyNewsId === item.id ? t('topnav.news.saving') : t('topnav.news.mark_read')}
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
          {newsMessage && <p className="hint">{newsMessage}</p>}
          {installMessage && <p className="hint">{installMessage}</p>}
        </div>
      </Modal>
    </header>
  );
}

