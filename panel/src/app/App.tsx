import { AuthProvider } from './auth';
import { RouterProvider } from 'react-router-dom';

import { router } from './routes';
import { I18nProvider } from '../i18n';

export function App() {
  return (
    <AuthProvider>
      <I18nProvider>
        <RouterProvider router={router} />
      </I18nProvider>
    </AuthProvider>
  );
}
