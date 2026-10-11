import { useCallback, useEffect, useRef, useState } from 'react';
import { Api, errorMessage } from './api';
import { desktopWorker } from './desktopWorker';
import { canPauseDevice, deviceStatus } from './deviceStatus';
import type { ModelStatus, WorkerStatus } from './desktopWorker';
import type { Device, Limits, Session } from './types';

const idle: WorkerStatus = { phase: 'stopped', message: 'Connect to get ready. Sharing starts only when you choose.' };

const megabytes = (bytes: number) => `${Math.round(bytes / 1_000_000)} MB`;

export function DesktopWorkerPanel({ session, api, devices, now, onDeviceIdChange }: { session: Session; api: Api; devices: Device[]; now: number; onDeviceIdChange: (id: string | null) => void }) {
  const [projectRoot, setProjectRoot] = useState('');
  const [bundled, setBundled] = useState(false);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [modelPending, setModelPending] = useState(false);
  const modelActionPending = useRef(false);
  const [backend, setBackend] = useState('auto');
  const [status, setStatus] = useState<WorkerStatus>(idle);
  const [initialized, setInitialized] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<{ id: string; limits: Limits; dirty: boolean } | null>(null);
  const mounted = useRef(false);
  const actionPending = useRef(false);
  const latest = useRef(status);
  const bundledRef = useRef(false);
  const device = devices.find(item => item.id === status.deviceId);
  useEffect(() => { onDeviceIdChange(status.deviceId ?? null); }, [status.deviceId, onDeviceIdChange]);
  const active = status.phase === 'starting' || status.phase === 'connected';
  const limits = device && draft?.id === device.id ? draft.limits : device?.limits;
  const pausable = device ? canPauseDevice(device, now) : false;
  const validLimits = !!limits && Number.isInteger(limits.cpu_threads) && limits.cpu_threads >= 1 && limits.cpu_threads <= 8;
  const deviceId = device?.id;
  const cpuThreads = device?.limits.cpu_threads;
  const maxPixels = device?.limits.max_pixels;
  const sessionMinutes = device?.limits.session_minutes;

  useEffect(() => {
    if (!deviceId || cpuThreads == null || maxPixels == null || sessionMinutes == null) return;
    // Sync changed server settings without replacing an unfinished edit on every poll.
    setDraft(previous => previous?.id === deviceId && previous.dirty ? previous : {
      id: deviceId, limits: { cpu_threads: cpuThreads, max_pixels: maxPixels, session_minutes: sessionMinutes }, dirty: false,
    });
  }, [deviceId, cpuThreads, maxPixels, sessionMinutes]);

  function editLimits(patch: Partial<Limits>) {
    if (device && limits) setDraft({ id: device.id, limits: { ...limits, ...patch }, dirty: true });
  }

  async function updateSharing(enabled?: boolean) {
    if (actionPending.current || !device || !limits || (enabled !== false && !validLimits)) return;
    if (enabled === true && (!device.online || status.phase !== 'connected')) return;
    actionPending.current = true; setPending(true); setError('');
    try {
      const updated = await api.request<Device>(`/devices/${device.id}`, enabled === false
        ? { enabled: false } : { ...(enabled === true ? { enabled: true } : {}), limits }, 'PATCH');
      // If Leave won the race with Start, revoke the late acknowledgment as well.
      if (!mounted.current && enabled === true) await pauseDevice(updated.id);
      if (mounted.current && enabled !== false) setDraft({ id: updated.id, limits: updated.limits, dirty: false });
      // Sharing status comes from the next grid snapshot, never an optimistic success.
    } catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { actionPending.current = false; if (mounted.current) setPending(false); }
  }

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
    if (modelActionPending.current) return;
    modelActionPending.current = true; setModelPending(true); setError('');
    try { const next = await action(); if (mounted.current) setModel(next); }
    catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { modelActionPending.current = false; if (mounted.current) setModelPending(false); }
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
    <div className="section-title"><h3>This Mac · image creation</h3><span className="badge">{active ? (status.phase === 'starting' ? 'Starting…' : device ? deviceStatus(device, now) === 'Paused' ? 'Connected · paused' : deviceStatus(device, now) : 'Checking grid…') : status.phase === 'failed' ? 'Needs attention' : 'Disconnected'}</span></div>
    <p>{status.phase === 'connected' ? 'Ready when you are. Pause anytime.' : bundled ? 'Connect to get ready. Sharing starts paused.' : 'Connect your prepared worker. It starts paused.'}</p>
    {bundled && model?.phase !== 'ready' && <div className="model-setup stack">
      <div className="section-title"><h3>Image model</h3><span className="badge">{!model ? 'Checking…' : model.phase === 'downloading' ? 'Downloading' : model.phase === 'failed' ? 'Needs attention' : 'One-time setup'}</span></div>
      {model?.phase === 'downloading' && <><progress value={Math.min(model.downloadedBytes, model.expectedBytes)} max={model.expectedBytes} aria-label="Image model download" /><small>{megabytes(model.downloadedBytes)} of about {megabytes(model.expectedBytes)}</small></>}
      {model?.phase === 'failed' && <p className="error" role="alert">{model.message}</p>}
      {model && <div className="button-row">{model.phase === 'downloading'
        ? <button className="secondary" disabled={modelPending} onClick={() => void modelAction(() => desktopWorker.cancelModelDownload())}>Cancel download</button>
        : <button disabled={modelPending} onClick={() => void modelAction(() => desktopWorker.downloadModel())}>{modelPending ? 'Starting…' : 'Download model · 1 GB'}</button>}</div>}
      <small>Download once. Sharing stays off.</small>
    </div>}
    <div className="button-row">
      {status.phase !== 'connected' && <button disabled={!initialized || pending || active || (bundled ? model?.phase !== 'ready' || modelPending : !projectRoot.trim())} onClick={() => void connect()}>{pending && !active ? 'Connecting…' : 'Connect worker'}</button>}
      {status.phase === 'connected' && <button disabled={pending || !device || (!pausable && (!device.online || !validLimits))} onClick={() => void updateSharing(!pausable)}>{pending ? 'Updating…' : pausable ? 'Pause sharing' : 'Start sharing'}</button>}
      {status.phase !== 'stopped' && <button className="secondary" disabled={!initialized || pending} onClick={() => void disconnect()}>Disconnect</button>}
    </div>
    {device && limits && <details><summary>Sharing limits</summary><div className="stack">
      <div className="limits">
        <label>CPU threads<input type="number" min="1" max="8" value={limits.cpu_threads} disabled={pending} onChange={event => editLimits({ cpu_threads: Number(event.target.value) })} /></label>
        <label>Largest image<select value={limits.max_pixels} disabled={pending} onChange={event => editLimits({ max_pixels: Number(event.target.value) })}><option value={65536}>256 × 256</option><option value={147456}>384 × 384</option><option value={262144}>512 × 512</option></select></label>
        <label>Share for<select value={limits.session_minutes} disabled={pending} onChange={event => editLimits({ session_minutes: Number(event.target.value) })}>{[5, 15, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes} minutes</option>)}</select></label>
      </div>
      <small>CPU threads do not limit GPU or memory use.</small>
      <button className="secondary" disabled={pending || !validLimits || !draft?.dirty} onClick={() => void updateSharing()}>Save limits</button>
    </div></details>}
    {error && <p className="error" role="alert">{error}</p>}
    {status.phase === 'failed' && <p className="error" role="alert">{status.message}</p>}
    <details><summary>Worker setup & details</summary><div className="stack">
      {!bundled && <label>PocketGrid folder<input value={projectRoot} onChange={event => setProjectRoot(event.target.value)} disabled={pending || active || !initialized} placeholder="/path/to/pocketgrid" spellCheck={false} autoComplete="off" /></label>}
      <label>Processor<select value={backend} onChange={event => setBackend(event.target.value)} disabled={pending || active}><option value="auto">Automatic</option><option value="mps">Apple GPU</option><option value="cpu">CPU</option></select></label>
      <small>{bundled ? 'Connect uses the downloaded model offline. Model files come from Hugging Face.' : 'Requires a prepared Python environment and cached Tiny-SD model.'}</small>
      <p>{status.message}{status.backend && ` Processor: ${status.backend.toUpperCase()}.`}</p>
      <small>Sharing can continue in the background until your session ends. Disconnect releases model memory.</small>
    </div></details>
  </div>;
}
