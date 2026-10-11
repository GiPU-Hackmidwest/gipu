import { useCallback, useEffect, useRef, useState } from 'react';
import { Api, errorMessage } from './api';
import { desktopWorker } from './desktopWorker';
import type { WorkerStatus } from './desktopWorker';
import type { Device, Session } from './types';

const idle: WorkerStatus = { phase: 'stopped', message: 'Connect your installed image worker, then start sharing from its device card.' };

export function DesktopWorkerPanel({ session, api, devices }: { session: Session; api: Api; devices: Device[] }) {
  const [projectRoot, setProjectRoot] = useState('');
  const [backend, setBackend] = useState('auto');
  const [status, setStatus] = useState<WorkerStatus>(idle);
  const [initialized, setInitialized] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(false);
  const actionPending = useRef(false);
  const latest = useRef(status);
  const device = devices.find(item => item.id === status.deviceId);
  const active = status.phase === 'starting' || status.phase === 'connected';

  const pauseDevice = useCallback(async (id?: string | null) => {
    if (!id) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    try { await api.request(`/devices/${id}`, { enabled: false }, 'PATCH', controller.signal); }
    finally { clearTimeout(timeout); }
  }, [api]);

  useEffect(() => {
    mounted.current = true;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const remember = (next: WorkerStatus) => { latest.current = next; setStatus(next); };
    const poll = async () => {
      try {
        const next = await desktopWorker.status();
        if (!disposed && !actionPending.current) remember(next);
      } catch (error) { if (!disposed) setError(errorMessage(error)); }
      if (!disposed) timer = setTimeout(poll, 2000);
    };
    void (async () => {
      // Reloading the interface never resumes an old contribution session.
      await desktopWorker.disconnect(stopped => pauseDevice(stopped.deviceId).catch(() => {}));
      const defaults = await desktopWorker.defaults();
      if (!disposed) { setProjectRoot(defaults.projectRoot); remember(idle); }
    })().catch(error => { if (!disposed) setError(errorMessage(error)); }).finally(() => {
      if (!disposed) { setInitialized(true); void poll(); }
    });
    const stop = () => {
      void desktopWorker.disconnect(next => pauseDevice(next.deviceId ?? latest.current.deviceId)).catch(() => {});
    };
    window.addEventListener('pagehide', stop);
    return () => {
      disposed = true; mounted.current = false; clearTimeout(timer);
      window.removeEventListener('pagehide', stop); stop();
    };
  }, [pauseDevice]);

  async function connect() {
    if (actionPending.current) return;
    actionPending.current = true; setPending(true); setError('');
    try {
      const next = await desktopWorker.connect({ projectRoot: projectRoot.trim(), server: session.server, sessionToken: session.token, backend });
      if (mounted.current) { latest.current = next; setStatus(next); }
    } catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { actionPending.current = false; if (mounted.current) setPending(false); }
  }

  async function disconnect() {
    if (actionPending.current) return;
    actionPending.current = true; setPending(true); setError('');
    try {
      // Kill the local process before waiting for the coordinator to acknowledge Pause.
      const previousId = latest.current.deviceId;
      await desktopWorker.disconnect(async next => {
        if (mounted.current) { latest.current = next; setStatus(next); }
        try { await pauseDevice(next.deviceId ?? previousId); }
        catch { if (mounted.current && next.phase === 'stopped') setError('The local worker stopped. The coordinator could not confirm Pause; unfinished work will recover after its lease expires.'); }
      });
    } catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { actionPending.current = false; if (mounted.current) setPending(false); }
  }

  return <div className="local-worker stack">
    <div className="section-title"><h3>Image generation on this Mac</h3><span className="badge">{active ? (device?.enabled ? 'Sharing' : status.phase === 'starting' ? 'Starting worker' : 'Connected · paused') : status.phase === 'failed' ? 'Worker needs attention' : 'Disconnected'}</span></div>
    <p>Connect the prepared Python worker to this account. Its device card below lets you set limits and start sharing.</p>
    <details><summary>Installed worker settings</summary><div className="stack">
      <label>PocketGrid project folder<input value={projectRoot} onChange={event => setProjectRoot(event.target.value)} disabled={pending || active || !initialized} placeholder="/path/to/pocketgrid" spellCheck={false} autoComplete="off" /></label>
      <label>Processor<select value={backend} onChange={event => setBackend(event.target.value)} disabled={pending || active}><option value="auto">Automatic</option><option value="mps">Apple GPU</option><option value="cpu">CPU</option></select></label>
      <small>The Python environment and cached Tiny-SD model must already be prepared in this folder. This action does not download model files.</small>
    </div></details>
    <div className="button-row"><button disabled={!initialized || pending || active || !projectRoot.trim()} onClick={() => void connect()}>{pending && !active ? 'Connecting…' : 'Connect installed worker'}</button><button className="secondary" disabled={!initialized || pending || status.phase === 'stopped'} onClick={() => void disconnect()}>Disconnect worker</button></div>
    <p className={status.phase === 'failed' ? 'error' : 'worker-status'} role={status.phase === 'failed' ? 'alert' : 'status'}>{status.message}{status.backend && ` Processor: ${status.backend.toUpperCase()}.`}</p>
    {error && <p className="error" role="alert">{error}</p>}
    <small>Connecting loads the model into memory and leaves sharing paused. Sharing can continue while this app is in the background, within your chosen session limits. Disconnecting, leaving the grid or quitting stops this worker and releases its model memory.</small>
  </div>;
}
