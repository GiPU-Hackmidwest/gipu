import { useCallback, useEffect, useRef, useState } from 'react';
import { Api, errorMessage } from './api';
import { desktopWorker } from './desktopWorker';
import type { ModelStatus, WorkerStatus } from './desktopWorker';
import type { Device, Session } from './types';

const idle: WorkerStatus = { phase: 'stopped', message: 'Connect your installed image worker, then start sharing from its device card.' };
const megabytes = (bytes: number) => `${Math.round(bytes / 1_000_000)} MB`;

export function DesktopWorkerPanel({ session, api, devices }: { session: Session; api: Api; devices: Device[] }) {
  const [projectRoot, setProjectRoot] = useState('');
  const [bundled, setBundled] = useState(false);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [backend, setBackend] = useState('auto');
  const [status, setStatus] = useState<WorkerStatus>(idle);
  const [initialized, setInitialized] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(false);
  const actionPending = useRef(false);
  const latest = useRef(status);
  const bundledRef = useRef(false);
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
        if (bundledRef.current) { const nextModel = await desktopWorker.modelStatus(); if (!disposed) setModel(nextModel); }
      } catch (error) { if (!disposed) setError(errorMessage(error)); }
      if (!disposed) timer = setTimeout(poll, 2000);
    };
    void (async () => {
      // Reloading the interface never resumes an old contribution session.
      await desktopWorker.disconnect(stopped => pauseDevice(stopped.deviceId).catch(() => {}));
      const defaults = await desktopWorker.defaults();
      if (!disposed) { setProjectRoot(defaults.projectRoot); setBundled(defaults.bundled); bundledRef.current = defaults.bundled; remember(idle); }
      if (defaults.bundled) { const current = await desktopWorker.modelStatus(); if (!disposed) setModel(current); }
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

  async function modelAction(action: () => Promise<ModelStatus>) {
    setError('');
    try { const next = await action(); if (mounted.current) setModel(next); }
    catch (error) { if (mounted.current) setError(errorMessage(error)); }
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
    <p>{bundled ? 'This app includes the image worker. Download the model once, then connect it to this account.' : 'Connect the prepared Python worker to this account.'} Its device card below lets you set limits and start sharing.</p>
    {bundled && model && model.phase !== 'ready' && <div className="stack">
      <p className={model.phase === 'failed' ? 'error' : 'worker-status'} role={model.phase === 'failed' ? 'alert' : 'status'}>{model.message}</p>
      {model.phase === 'downloading' && <><progress value={Math.min(model.downloadedBytes, model.expectedBytes)} max={model.expectedBytes} /><small>{megabytes(model.downloadedBytes)} of about {megabytes(model.expectedBytes)}</small></>}
      <div className="button-row">{model.phase === 'downloading'
        ? <button className="secondary" onClick={() => void modelAction(() => desktopWorker.cancelModelDownload())}>Cancel download</button>
        : <button onClick={() => void modelAction(() => desktopWorker.downloadModel())}>Download image model (about 1 GB)</button>}</div>
      <small>Downloads the pinned Tiny-SD model from Hugging Face into PocketGrid’s app data. Downloading does not share this Mac or join it to the grid.</small>
    </div>}
    <details><summary>{bundled ? 'Worker settings' : 'Installed worker settings'}</summary><div className="stack">
      {!bundled && <label>PocketGrid project folder<input value={projectRoot} onChange={event => setProjectRoot(event.target.value)} disabled={pending || active || !initialized} placeholder="/path/to/pocketgrid" spellCheck={false} autoComplete="off" /></label>}
      <label>Processor<select value={backend} onChange={event => setBackend(event.target.value)} disabled={pending || active}><option value="auto">Automatic</option><option value="mps">Apple GPU</option><option value="cpu">CPU</option></select></label>
      <small>{bundled ? 'Connect uses only the downloaded model and never downloads files.' : 'The Python environment and cached Tiny-SD model must already be prepared in this folder. This action does not download model files.'}</small>
    </div></details>
    <div className="button-row"><button disabled={!initialized || pending || active || (bundled ? model?.phase !== 'ready' : !projectRoot.trim())} onClick={() => void connect()}>{pending && !active ? 'Connecting…' : bundled ? 'Connect worker' : 'Connect installed worker'}</button><button className="secondary" disabled={!initialized || pending || status.phase === 'stopped'} onClick={() => void disconnect()}>Disconnect worker</button></div>
    <p className={status.phase === 'failed' ? 'error' : 'worker-status'} role={status.phase === 'failed' ? 'alert' : 'status'}>{status.message}{status.backend && ` Processor: ${status.backend.toUpperCase()}.`}</p>
    {error && <p className="error" role="alert">{error}</p>}
    <small>Connecting loads the model into memory and leaves sharing paused. Sharing can continue while this app is in the background, within your chosen session limits. Disconnecting, leaving the grid or quitting stops this worker and releases its model memory.</small>
  </div>;
}
