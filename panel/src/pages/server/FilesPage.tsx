import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { Card } from '../../components/ui/Card';
import { FileManager } from '../../components/server/FileManager';
import { useI18n } from '../../i18n';

export function FilesPage() {
  const serverId = DEFAULT_SERVER_ID;
  const { can } = useAuth();
  const { t } = useI18n();

  if (!can('files.read', serverId)) {
    return (
      <section className="page">
        <Card title={t('files.page.title')} subtitle={t('common.server_subtitle', { server_id: serverId })}>
          <p className="hint hint--error">{t('files.page.error.read_forbidden')}</p>
        </Card>
      </section>
    );
  }

  return (
    <section className="page">
      <Card title={t('files.page.title')} subtitle={t('common.server_subtitle', { server_id: serverId })}>
        <FileManager serverId={serverId} />
      </Card>
    </section>
  );
}
