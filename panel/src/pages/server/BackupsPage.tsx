import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { BackupList } from '../../components/server/BackupList';
import { Card } from '../../components/ui/Card';
import { useI18n } from '../../i18n';

export function BackupsPage() {
  const serverId = DEFAULT_SERVER_ID;
  const { can } = useAuth();
  const { t } = useI18n();

  if (!can('files.read', serverId)) {
    return (
      <section className="page">
        <Card title={t('backups.page.title')} subtitle={t('common.server_subtitle', { server_id: serverId })}>
          <p className="hint hint--error">{t('backups.page.error.read_forbidden')}</p>
        </Card>
      </section>
    );
  }

  return (
    <section className="page">
      <Card title={t('backups.page.title')} subtitle={t('common.server_subtitle', { server_id: serverId })}>
        <BackupList serverId={serverId} />
      </Card>
    </section>
  );
}
