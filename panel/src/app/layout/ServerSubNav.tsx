import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth';
import { DEFAULT_SERVER_ID } from '../defaultServer';
import { useI18n } from '../../i18n';
import type { AppPermission } from '../permissions';

type ServerTabLink = {
  to: string;
  labelKey: string;
  permission?: AppPermission;
};

const links: ServerTabLink[] = [
  { to: 'console', labelKey: 'server.tabs.console', permission: 'logs.read' },
  { to: 'files', labelKey: 'server.tabs.files', permission: 'files.read' },
  { to: 'backups', labelKey: 'server.tabs.backups', permission: 'files.read' },
  { to: 'config', labelKey: 'server.tabs.config', permission: 'files.read' },
  { to: 'env', labelKey: 'server.tabs.env', permission: 'server.read' },
  { to: 'activity', labelKey: 'server.tabs.activity', permission: 'activity.read' },
  { to: 'news', labelKey: 'server.tabs.news', permission: 'news.read' },
  { to: 'options', labelKey: 'server.tabs.options' },
];

export function ServerSubNav() {
  const { can } = useAuth();
  const { t } = useI18n();
  const serverId = DEFAULT_SERVER_ID;
  const visibleLinks = links.filter((link) => !link.permission || can(link.permission, serverId));

  return (
    <nav className="server-subnav" aria-label={t('server.tabs.aria')}>
      {visibleLinks.map((link) => (
        <NavLink
          key={link.to}
          to={`/${link.to}`}
          className={({ isActive }) => (isActive ? 'server-subnav__item is-active' : 'server-subnav__item')}
        >
          {t(link.labelKey)}
        </NavLink>
      ))}
    </nav>
  );
}
