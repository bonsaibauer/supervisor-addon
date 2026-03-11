import { Navigate, Outlet, createBrowserRouter, useLocation } from 'react-router-dom';

import { useAuth } from './auth';
import { ServerSubNav } from './layout/ServerSubNav';
import { TopNav } from './layout/TopNav';
import type { AppPermission } from './permissions';
import { useI18n } from '../i18n';
import { LoginPage } from '../pages/LoginPage';
import { ChangePasswordPage } from '../pages/ChangePasswordPage';
import { StatusPage } from '../pages/StatusPage';
import { ActivityPage } from '../pages/server/ActivityPage';
import { BackupsPage } from '../pages/server/BackupsPage';
import { ConfigPage } from '../pages/server/ConfigPage';
import { ConsolePage } from '../pages/server/ConsolePage';
import { EnvPage } from '../pages/server/EnvPage';
import { FilesPage } from '../pages/server/FilesPage';
import { NewsPage } from '../pages/server/NewsPage';
import { OptionsPage } from '../pages/server/OptionsPage';

function AuthGate() {
  const { ready, isAuthenticated, mustChangePassword } = useAuth();
  const { t } = useI18n();
  const location = useLocation();

  if (!ready) {
    return <div className="auth-splash">{t('route.checking_session')}</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (mustChangePassword && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }

  return <Outlet />;
}

function LoginGate() {
  const { ready, isAuthenticated, mustChangePassword } = useAuth();
  const { t } = useI18n();

  if (!ready) {
    return <div className="auth-splash">{t('route.checking_session')}</div>;
  }

  if (isAuthenticated) {
    if (mustChangePassword) {
      return <Navigate to="/change-password" replace />;
    }
    return <Navigate to="/" replace />;
  }

  return <LoginPage />;
}

function RootLayout() {
  return (
    <div className="app-shell">
      <TopNav />
      <main className="container">
        <Outlet />
      </main>
    </div>
  );
}

function ServerLayout() {
  return (
    <div className="server-layout">
      <ServerSubNav />
      <Outlet />
    </div>
  );
}

function PermissionGate({ permission }: { permission: AppPermission }) {
  const { can } = useAuth();
  if (!can(permission)) {
    return <Navigate to="/console" replace />;
  }
  return <Outlet />;
}

export const router = createBrowserRouter([
  {
    path: '/status/:code',
    element: <StatusPage />,
  },
  {
    path: '/login',
    element: <LoginGate />,
  },
  {
    element: <AuthGate />,
    children: [
      {
        path: '/',
        element: <RootLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="/console" replace />,
          },
          {
            path: 'change-password',
            element: <ChangePasswordPage />,
          },
          {
            element: <ServerLayout />,
            children: [
              {
                path: 'console',
                element: <ConsolePage />,
              },
              {
                element: <PermissionGate permission="files.read" />,
                children: [{ path: 'files', element: <FilesPage /> }],
              },
              {
                element: <PermissionGate permission="files.read" />,
                children: [{ path: 'backups', element: <BackupsPage /> }],
              },
              {
                element: <PermissionGate permission="files.read" />,
                children: [{ path: 'config', element: <ConfigPage /> }],
              },
              {
                element: <PermissionGate permission="server.read" />,
                children: [{ path: 'env', element: <EnvPage /> }],
              },
              {
                path: 'activity',
                element: <ActivityPage />,
              },
              {
                path: 'news',
                element: <NewsPage />,
              },
              {
                path: 'options',
                element: <OptionsPage />,
              },
            ],
          },
          { path: '*', element: <Navigate to="/console" replace /> },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/status/404" replace />,
  },
]);
