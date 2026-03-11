import { useEffect, useRef, useState } from 'react';

import { useAuth } from '../../app/auth';
import { DEFAULT_SERVER_ID } from '../../app/defaultServer';
import { getServer, getServerStats } from '../../api/servers';
import type { RuntimeStats, ServerDetails } from '../../api/types';
import { Console } from '../../components/server/Console';
import { PowerButtons } from '../../components/server/PowerButtons';
import { Card } from '../../components/ui/Card';
import { useI18n } from '../../i18n';

function formatMiB(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    return '-';
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function clampPercent(value: number | null | undefined): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function sparklinePoints(values: number[], width: number, height: number): string {
  if (!values.length) return '';
  if (values.length === 1) return `0,${height / 2} ${width},${height / 2}`;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const rawRange = max - min;
  const paddedRange = Math.max(rawRange, 8);
  const minScale = Math.max(0, min - paddedRange * 0.15);
  const maxScale = Math.min(100, max + paddedRange * 0.15);
  const scaleRange = Math.max(1, maxScale - minScale);
  const stepX = width / (values.length - 1);
  return values
    .map((value, index) => {
      const x = index * stepX;
      const normalized = (clampPercent(value) - minScale) / scaleRange;
      const y = height - normalized * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

function loadLevel(percent: number): 'ok' | 'warn' | 'danger' {
  if (percent >= 85) return 'danger';
  if (percent >= 65) return 'warn';
  return 'ok';
}

type RuntimeStatusMeta = {
  pillClass: string;
  dotClass: string;
};

function runtimeStatusMeta(status: string): RuntimeStatusMeta {
  const normalized = status.trim().toUpperCase();
  switch (normalized) {
    case 'RUNNING':
      return { pillClass: 'status-pill status-pill--set', dotClass: 'status-pill__dot status-pill__dot--running' };
    case 'STARTING':
      return { pillClass: 'status-pill status-pill--warn', dotClass: 'status-pill__dot status-pill__dot--starting' };
    case 'STOPPING':
      return { pillClass: 'status-pill status-pill--warn', dotClass: 'status-pill__dot status-pill__dot--stopping' };
    case 'BACKOFF':
    case 'FATAL':
      return { pillClass: 'status-pill status-pill--danger', dotClass: 'status-pill__dot status-pill__dot--danger' };
    case 'STOPPED':
    case 'EXITED':
      return { pillClass: 'status-pill status-pill--idle', dotClass: 'status-pill__dot status-pill__dot--idle' };
    case '':
    case 'UNKNOWN':
      return { pillClass: 'status-pill status-pill--neutral', dotClass: 'status-pill__dot status-pill__dot--neutral' };
    default:
      return { pillClass: 'status-pill status-pill--neutral', dotClass: 'status-pill__dot status-pill__dot--neutral' };
  }
}

export function ConsolePage() {
  const serverId = DEFAULT_SERVER_ID;
  const { t } = useI18n();
  const { can } = useAuth();
  const canReadLogs = can('logs.read', serverId);
  const canReadServerRuntime = can('server.read', serverId);
  const consoleCanWrite = can('server.control', serverId);

  const [server, setServer] = useState<ServerDetails | null>(null);
  const [stats, setStats] = useState<RuntimeStats | null>(null);
  const [ramHistory, setRamHistory] = useState<number[]>([]);
  const [celebrateRunning, setCelebrateRunning] = useState(false);
  const previousStatusRef = useRef('unknown');
  const celebrationTimerRef = useRef<number | null>(null);
  const runtimeStatus = server?.process_info?.statename || 'unknown';
  const statusMeta = runtimeStatusMeta(runtimeStatus);
  const runtimeStatusLabel = t(`console.runtime_status.${runtimeStatus.trim().toLowerCase()}`) || runtimeStatus;

  useEffect(() => {
    if (!serverId || !canReadLogs || !canReadServerRuntime) return undefined;

    let active = true;
    const refresh = async () => {
      const [serverResult, statsResult] = await Promise.allSettled([getServer(serverId), getServerStats(serverId)]);
      if (!active) return;

      if (serverResult.status === 'fulfilled') {
        setServer(serverResult.value);
      } else {
        setServer(null);
      }

      if (statsResult.status === 'fulfilled') {
        setStats(statsResult.value);
      } else {
        setStats(null);
      }
    };

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 3000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [serverId, canReadLogs, canReadServerRuntime]);

  useEffect(() => {
    if (stats?.available === true) {
      setRamHistory((previous) => [...previous, clampPercent(stats.memory_percent)].slice(-24));
    }
  }, [stats]);

  useEffect(() => {
    const next = runtimeStatus.trim().toUpperCase();
    const prev = previousStatusRef.current.trim().toUpperCase();
    if (prev === 'STARTING' && next === 'RUNNING') {
      setCelebrateRunning(true);
      if (celebrationTimerRef.current) {
        window.clearTimeout(celebrationTimerRef.current);
      }
      celebrationTimerRef.current = window.setTimeout(() => {
        setCelebrateRunning(false);
      }, 3000);
    }
    previousStatusRef.current = next;
  }, [runtimeStatus]);

  useEffect(() => {
    return () => {
      if (celebrationTimerRef.current) {
        window.clearTimeout(celebrationTimerRef.current);
      }
    };
  }, []);

  const statsAvailable = stats?.available === true;
  const cpuPercent = statsAvailable ? clampPercent(stats.cpu_percent) : 0;
  const ramPercent = statsAvailable ? clampPercent(stats.memory_percent) : 0;
  const cpuCoresPercent = statsAvailable ? stats.cpu_cores_percent.map((value) => clampPercent(value)) : [];
  const cpuCoresTotal = statsAvailable ? stats.cpu_cores_total : 0;
  const cpuUsedCores = statsAvailable ? Math.max(0, stats.cpu_used_cores) : 0;
  const cpuPeakCorePercent = cpuCoresPercent.length ? Math.max(...cpuCoresPercent) : cpuPercent;
  const cpuPeakCoreIndex = cpuCoresPercent.length ? cpuCoresPercent.indexOf(cpuPeakCorePercent) : -1;
  const cpuLevel = loadLevel(cpuPercent);
  const ramLevel = loadLevel(ramPercent);
  const ramPeak = ramHistory.length ? Math.max(...ramHistory) : ramPercent;
  const cpuLabel = statsAvailable ? `${stats.cpu_percent.toFixed(1)}%` : '-';
  const cpuUsedLabel = statsAvailable ? `${cpuUsedCores.toFixed(1)} / ${cpuCoresTotal}` : '-';
  const ramLabel = statsAvailable ? `${formatMiB(stats.memory_used_bytes)} / ${formatMiB(stats.memory_limit_bytes)}` : '-';

  if (!canReadLogs) {
    return (
      <section className="page">
        <Card title={serverId} subtitle={t('console.page.access_denied.title')}>
          <p className="hint hint--error">{t('console.page.access_denied.message')}</p>
        </Card>
      </section>
    );
  }

  return (
    <section className="page">
      <Card title={serverId} subtitle={t('console.page.runtime_overview')}>
        <div style={{ position: 'relative' }}>
          {celebrateRunning && (
            <div className="console-fireworks" aria-hidden="true">
              <span className="console-fireworks__burst console-fireworks__burst--a" />
              <span className="console-fireworks__burst console-fireworks__burst--b" />
              <span className="console-fireworks__burst console-fireworks__burst--c" />
            </div>
          )}
        {canReadServerRuntime && (
          <div className="runtime-overview">
            <div className="runtime-fields">
              <div className="runtime-field">
                <span className="runtime-field__label">{t('console.page.program_label')}</span>
                <span className="runtime-field__value">{server?.runtime_program || t('console.page.unknown')}</span>
              </div>
              <div className="runtime-field">
                <span className="runtime-field__label">{t('console.page.status_label')}</span>
                <span className={statusMeta.pillClass}>
                  <span className={statusMeta.dotClass} aria-hidden="true" />
                  {runtimeStatusLabel}
                </span>
              </div>
            </div>
            <div className="runtime-divider" />
            <PowerButtons
              serverId={serverId}
              onDone={() => void getServer(serverId).then(setServer).catch(() => setServer(null))}
              showBackupWarningInline={false}
            />
            <div className="runtime-divider" />
            <div className="runtime-metrics">
              <div className="runtime-kpi-grid">
                <article className={`runtime-kpi runtime-kpi--cpu runtime-kpi--${cpuLevel}`}>
                  <header className="runtime-kpi__header">
                    <span className="runtime-kpi__label">{t('console.page.cpu')}</span>
                    <span className="runtime-kpi__value">{cpuLabel}</span>
                  </header>
                  <header className="runtime-kpi__meta">
                    <span className="runtime-kpi__peak">{t('console.page.cpu_cores', { cores: cpuUsedLabel })}</span>
                    <span className="runtime-kpi__peak">
                      {cpuPeakCoreIndex >= 0
                        ? t('console.page.cpu_peak_core', { core_index: cpuPeakCoreIndex })
                        : t('console.page.cpu_peak')} {cpuPeakCorePercent.toFixed(1)}%
                    </span>
                  </header>
                  <div className="runtime-kpi__bar">
                    <span className="runtime-kpi__fill" style={{ width: `${cpuPercent}%` }} />
                  </div>
                  {statsAvailable ? (
                    <div className="runtime-core-grid" role="list" aria-label={t('console.page.cpu_core_usage_aria')}>
                      {cpuCoresPercent.map((corePercent, index) => {
                        const coreLevel = loadLevel(corePercent);
                        const peakClass = index === cpuPeakCoreIndex ? ' runtime-core--peak' : '';
                        return (
                          <div key={`core-${index}`} className={`runtime-core runtime-core--${coreLevel}${peakClass}`} role="listitem">
                            <span className="runtime-core__label">C{index}</span>
                            <span className="runtime-core__bar">
                              <span className="runtime-core__fill" style={{ width: `${corePercent}%` }} />
                            </span>
                            <span className="runtime-core__value">{corePercent.toFixed(0)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="runtime-line runtime-line--muted">{t('console.page.cpu_stats_unavailable')}</p>
                  )}
                </article>

                <article className={`runtime-kpi runtime-kpi--ram runtime-kpi--${ramLevel}`}>
                  <header className="runtime-kpi__header">
                    <span className="runtime-kpi__label">{t('console.page.ram')}</span>
                    <span className="runtime-kpi__value">{ramLabel}</span>
                  </header>
                  <header className="runtime-kpi__meta">
                    <span className="runtime-kpi__peak">{t('console.page.ram_peak', { percent: ramPeak.toFixed(2) })}</span>
                  </header>
                  <div className="runtime-kpi__bar">
                    <span className="runtime-kpi__fill" style={{ width: `${ramPercent}%` }} />
                  </div>
                  <svg className="runtime-kpi__sparkline" viewBox="0 0 100 64" preserveAspectRatio="none" aria-hidden="true">
                    <polyline points={sparklinePoints(ramHistory, 100, 64)} />
                  </svg>
                </article>
              </div>
              {stats?.available === false && stats.error && (
                <p className="runtime-line runtime-line--muted">{t('console.page.stats_error', { error: stats.error })}</p>
              )}
            </div>
          </div>
        )}
        {!canReadServerRuntime && <p className="hint">{t('console.page.read_only_runtime')}</p>}
        </div>
      </Card>

      <Card title={t('console.page.live_console.title')} subtitle={t('console.page.live_console.subtitle')}>
        <Console serverId={serverId} canWrite={consoleCanWrite} />
      </Card>
    </section>
  );
}
