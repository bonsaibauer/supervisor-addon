import { useEffect, useMemo, useRef, useState } from 'react';

import { streamLogUrl } from '../../api/servers';
import { buildAuthHeaders } from '../../api/client';
import { useI18n } from '../../i18n';
import { Button } from '../ui/Button';

interface Props {
  serverId: string;
  canWrite?: boolean;
}

type LogChannel = 'supervisor' | 'enshrouded';
const MAX_CONSOLE_BUFFER_CHARS = 2_000_000;

export function Console({ serverId, canWrite = false }: Props) {
  const { t } = useI18n();
  const [channel, setChannel] = useState<LogChannel>('supervisor');
  const [text, setText] = useState('');
  const [offset, setOffset] = useState(0);
  const [running, setRunning] = useState(true);
  const [error, setError] = useState('');
  const boxRef = useRef<HTMLPreElement | null>(null);
  const sourceRef = useRef<AbortController | null>(null);
  const offsetRef = useRef(0);

  const localizeErrorMessage = (value: string): string => {
    const translated = t(value);
    return translated || value;
  };

  useEffect(() => {
    setText('');
    setOffset(0);
    offsetRef.current = 0;
  }, [serverId, channel]);

  useEffect(() => {
    sourceRef.current?.abort();
    sourceRef.current = null;
    if (!running) return undefined;

    const controller = new AbortController();
    sourceRef.current = controller;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    const scheduleReconnect = () => {
      if (stopped || controller.signal.aborted) return;
      reconnectTimer = setTimeout(() => {
        void connect();
      }, 1000);
    };

    const handleEventBlock = (block: string) => {
      const lines = block.split('\n');
      let eventType = 'message';
      const dataLines: string[] = [];
      for (const line of lines) {
        if (!line || line.startsWith(':')) continue;
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
          continue;
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
      if (dataLines.length === 0) return;

      try {
        const payload = JSON.parse(dataLines.join('\n')) as {
          data?: string;
          error?: string;
          next_offset?: number;
        };
        if (eventType === 'error' || payload.error) {
          setError(payload.error || 'console.error.stream_event');
          return;
        }

        const chunk = String(payload.data || '');
        const nextOffset = Number(payload.next_offset ?? offsetRef.current);
        if (chunk) {
          setText((prev) => `${prev}${chunk}`.slice(-MAX_CONSOLE_BUFFER_CHARS));
        }
        offsetRef.current = nextOffset;
        setOffset(nextOffset);
        setError('');
      } catch {
        setError('console.error.malformed_event');
      }
    };

    const connect = async () => {
      if (stopped || controller.signal.aborted) return;
      const url = streamLogUrl(serverId, channel, offsetRef.current);

      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: buildAuthHeaders(),
          credentials: 'same-origin',
          signal: controller.signal,
        });
        if (!response.ok) {
          let detail = '';
          try {
            const payload = (await response.json()) as { detail?: string };
            detail = typeof payload?.detail === 'string' ? payload.detail : '';
          } catch {
            detail = '';
          }
          throw new Error(detail || t('console.error.stream_request_failed_http', { status: response.status }));
        }
        if (!response.body) {
          throw new Error(t('console.error.stream_no_body'));
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!stopped && !controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          if (!value) continue;
          buffer += decoder.decode(value, { stream: true });
          let split = buffer.indexOf('\n\n');
          while (split !== -1) {
            const block = buffer.slice(0, split).trim();
            if (block) {
              handleEventBlock(block);
            }
            buffer = buffer.slice(split + 2);
            split = buffer.indexOf('\n\n');
          }
        }

        if (!stopped && !controller.signal.aborted) {
          setError('console.error.disconnected_reconnecting');
          scheduleReconnect();
        }
      } catch (streamError) {
        if (controller.signal.aborted || stopped) return;
        setError(streamError instanceof Error ? streamError.message : 'console.error.disconnected_reconnecting');
        scheduleReconnect();
      }
    };

    void connect();

    return () => {
      stopped = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      controller.abort();
      if (sourceRef.current === controller) {
        sourceRef.current = null;
      }
    };
  }, [serverId, channel, running]);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [text]);

  useEffect(
    () => () => {
      sourceRef.current?.abort();
      sourceRef.current = null;
    },
    []
  );

  const status = useMemo(() => (running ? t('console.status.live_sse') : t('console.status.paused')), [running, t]);
  const channelLabel = channel === 'supervisor' ? t('console.channel.supervisor') : t('console.channel.enshrouded');

  return (
    <div>
      <div className="console-toolbar">
        <div className="segmented">
          <button
            className={channel === 'supervisor' ? 'is-active' : ''}
            onClick={() => setChannel('supervisor')}
            type="button"
          >
            {t('console.channel.supervisor')}
          </button>
          <button
            className={channel === 'enshrouded' ? 'is-active' : ''}
            onClick={() => setChannel('enshrouded')}
            type="button"
          >
            {t('console.channel.enshrouded')}
          </button>
        </div>
        <div className="console-toolbar__actions">
          <span className="chip chip--muted">{t('console.toolbar.channel', { channel: channelLabel })}</span>
          <span className="badge">{status}</span>
          <span className="chip chip--muted">{t('console.toolbar.offset', { offset })}</span>
          {canWrite && (
            <Button variant="ghost" onClick={() => setRunning((prev) => !prev)}>
              {running ? t('console.button.pause') : t('console.button.resume')}
            </Button>
          )}
          {canWrite && (
            <Button
              variant="ghost"
              onClick={() => {
              setText('');
              setOffset(0);
              offsetRef.current = 0;
              sourceRef.current?.abort();
              if (running) {
                setRunning(false);
                setTimeout(() => setRunning(true), 0);
                }
              }}
            >
              {t('console.button.clear')}
            </Button>
          )}
        </div>
      </div>

      {error && <p className="hint hint--error">{localizeErrorMessage(error)}</p>}

      <pre ref={boxRef} className="console-box">
        {text || t('console.empty')}
      </pre>
    </div>
  );
}
