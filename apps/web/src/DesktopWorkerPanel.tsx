import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Api, errorMessage } from './api';
import { desktopWorker } from './desktopWorker';
import { canPauseDevice, deviceStatus } from './deviceStatus';
import { ContributionToggle } from './ContributionToggle';
import { connectAndStartContribution, reconcileAcknowledgedDevice } from './contributionLifecycle';
import type { DeviceAcknowledgement } from './contributionLifecycle';
import type { ModelStatus, WorkerStatus } from './desktopWorker';
import type { Device, Limits, Session, Snapshot } from './types';

const idle: WorkerStatus = { phase: 'stopped', message: 'Image worker disconnected.' };
const megabytes = (bytes: number) => `${Math.round(bytes / 1_000_000)} MB`;

export function DesktopWorkerPanel({ session, api, devices, now, onDeviceIdChange, developerTarget }: { session: Session; api: Api; devices: Device[]; now: number; onDeviceIdChange: (id: string | null) => void; developerTarget: HTMLElement | null }) {
  const [projectRoot, setProjectRoot] = useState('');
  const [bundled, setBundled] = useState(false);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [modelPending, setModelPending] = useState(false);
  const [confirmDownload, setConfirmDownload] = useState(false);
  const modelActionPending = useRef(false);
  const confirmButton = useRef<HTMLButtonElement>(null);
  const confirmationId = useId();
  const [backend, setBackend] = useState('auto');
  const [status, setStatus] = useState<WorkerStatus>(idle);
  const [initialized, setInitialized] = useState(false);
  const [pending, setPending] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<{ id: string; limits: Limits; dirty: boolean } | null>(null);
  const mounted = useRef(false);
  const actionPending = useRef(false);
  const latest = useRef(status);
  const bundledRef = useRef(false);
  const intentEpoch = useRef(0);
  const startOperation = useRef<Promise<string | null> | null>(null);
  const latestDraft = useRef(draft);
  latestDraft.current = draft;
  const [acknowledgement, setAcknowledgement] = useState<DeviceAcknowledgement | null>(null);
  const latestAcknowledgement = useRef<DeviceAcknowledgement | null>(null);
  const acknowledge = useCallback((updated: Device) => {
    if (!mounted.current) return;
    const next = { device: updated, confirmedAt: null };
    latestAcknowledgement.current = next; setAcknowledgement(next);
  }, []);
  const device = reconcileAcknowledgedDevice(devices.find(item => item.id === status.deviceId), now,
    acknowledgement?.device.id === status.deviceId ? acknowledgement : null);
  useEffect(() => {
    if (acknowledgement?.confirmedAt != null && now >= acknowledgement.confirmedAt && latestAcknowledgement.current === acknowledgement) {
      latestAcknowledgement.current = null; setAcknowledgement(null);
    }
  }, [acknowledgement, now]);
  useEffect(() => { onDeviceIdChange(status.deviceId ?? null); }, [status.deviceId, onDeviceIdChange]);
  useEffect(() => { if (confirmDownload) confirmButton.current?.focus(); }, [confirmDownload]);
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
    setDraft(previous => previous?.id === deviceId && previous.dirty ? previous : {
      id: deviceId, limits: { cpu_threads: cpuThreads, max_pixels: maxPixels, session_minutes: sessionMinutes }, dirty: false,
    });
  }, [deviceId, cpuThreads, maxPixels, sessionMinutes]);

  function editLimits(patch: Partial<Limits>) {
    if (device && limits) setDraft({ id: device.id, limits: { ...limits, ...patch }, dirty: true });
  }

  const pauseDevice = useCallback(async (id?: string | null) => {
    if (!id) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    try { acknowledge(await api.request<Device>(`/devices/${id}`, { enabled: false }, 'PATCH', controller.signal)); }
    finally { clearTimeout(timeout); }
  }, [api, acknowledge]);

  useEffect(() => {
    mounted.current = true;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const remember = (next: WorkerStatus) => { latest.current = next; setStatus(next); };
    const poll = async () => {
      try {
        const next = await desktopWorker.status();
        if (!disposed && !actionPending.current) remember(next);
        if (bundledRef.current) {
          const nextModel = await desktopWorker.modelStatus();
          if (!disposed && !modelActionPending.current) setModel(nextModel);
        }
      } catch (error) { if (!disposed) setError(errorMessage(error)); }
      // Only a read begun after the acknowledged write can establish its fence.
      // Failed reads retain the response and retry; later snapshots may pause or expire it.
      const acknowledged = latestAcknowledgement.current;
      if (!disposed && acknowledged && acknowledged.confirmedAt === null && !actionPending.current) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 4000);
        try {
          const snapshot = await api.request<Snapshot>('/state', undefined, undefined, controller.signal);
          if (!disposed && latestAcknowledgement.current === acknowledged) {
            const current = snapshot.devices.find(item => item.id === acknowledged.device.id);
            if (current) {
              const next = { device: current, confirmedAt: snapshot.server_time };
              latestAcknowledgement.current = next; setAcknowledgement(next);
            }
          }
        } catch { /* The write succeeded; retry synchronization on the next poll. */ }
        finally { clearTimeout(timeout); }
      }
      if (!disposed) timer = setTimeout(poll, 2000);
    };
    void (async () => {
      // A mount always disconnects first; saved preferences never authorize Start.
      await desktopWorker.disconnect(stopped => pauseDevice(stopped.deviceId).catch(() => {}));
      const defaults = await desktopWorker.defaults();
      if (!disposed) { setProjectRoot(defaults.projectRoot); setBundled(defaults.bundled); bundledRef.current = defaults.bundled; remember(idle); }
      if (defaults.bundled) { const current = await desktopWorker.modelStatus(); if (!disposed) setModel(current); }
    })().catch(error => { if (!disposed) setError(errorMessage(error)); }).finally(() => {
      if (!disposed) { setInitialized(true); void poll(); }
    });
    const stop = () => {
      intentEpoch.current += 1;
      actionPending.current = false;
      if (!disposed) { setStarting(false); setPending(false); }
      const inFlightStart = startOperation.current;
      // Stop the process first. Fence a late HTTP enable and its corrective Pause
      // inside native serialization before another account may Connect.
      void desktopWorker.disconnect(async next => {
        await inFlightStart?.catch(() => {});
        await pauseDevice(next.deviceId ?? latest.current.deviceId);
        if (!disposed) remember(next);
      }).catch(() => {});
    };
    window.addEventListener('pagehide', stop);
    return () => {
      disposed = true; mounted.current = false; clearTimeout(timer);
      window.removeEventListener('pagehide', stop); stop();
    };
  }, [api, pauseDevice]);

  async function turnOn() {
    if (actionPending.current || modelActionPending.current || !initialized) return;
    if (bundled && model?.phase !== 'ready') { if (model && model.phase !== 'downloading') setConfirmDownload(true); return; }
    if (!bundled && !projectRoot.trim()) { setError('Prepare a worker in Developer options before creating images.'); return; }
    const epoch = ++intentEpoch.current;
    const cancelled = () => !mounted.current || intentEpoch.current !== epoch;
    actionPending.current = true; setPending(true); setStarting(true); setError('');
    const operation = connectAndStartContribution({
      connect: () => desktopWorker.connect({ projectRoot: projectRoot.trim(), server: session.server, sessionToken: session.token, backend }),
      status: () => desktopWorker.status(), cancelled, pause: pauseDevice,
      onStatus: next => { if (!cancelled()) { latest.current = next; setStatus(next); } },
      enable: async id => {
        // The native worker can become ready before the parent's next snapshot.
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 12_000);
        try {
          const snapshot = await api.request<Snapshot>('/state', undefined, undefined, controller.signal);
          const ready = snapshot.devices.find(item => item.id === id);
          if (!ready?.online) throw new Error('This Mac is offline. Try again.');
          if (cancelled()) return;
          const edited = latestDraft.current;
          const selected = edited?.id === id ? edited.limits : ready.limits;
          if (!Number.isInteger(selected.cpu_threads) || selected.cpu_threads < 1 || selected.cpu_threads > 8) throw new Error('Check CPU threads in Developer options.');
          const updated = await api.request<Device>(`/devices/${id}`, { enabled: true, limits: selected }, 'PATCH', controller.signal);
          if (!cancelled()) { acknowledge(updated); setDraft({ id: updated.id, limits: updated.limits, dirty: false }); }
        } finally { clearTimeout(timeout); }
      },
    });
    startOperation.current = operation;
    try { await operation; }
    catch (error) {
      if (!cancelled()) {
        setError(errorMessage(error));
        // A failed or ambiguous start must not leave computation running unseen.
        await desktopWorker.disconnect(next => pauseDevice(next.deviceId ?? latest.current.deviceId).catch(() => {})).then(next => {
          if (!cancelled()) { latest.current = next; setStatus(next); }
        }).catch(() => {});
      }
    } finally {
      if (startOperation.current === operation) startOperation.current = null;
      if (intentEpoch.current === epoch) { actionPending.current = false; if (mounted.current) { setPending(false); setStarting(false); } }
    }
  }

  async function turnOff(disconnect = false) {
    if (actionPending.current && !starting) return;
    const epoch = ++intentEpoch.current;
    const inFlightStart = startOperation.current;
    actionPending.current = true; setPending(true); setStarting(false); setError('');
    try {
      if (disconnect || inFlightStart || latest.current.phase === 'starting') {
        await desktopWorker.disconnect(async next => {
          await inFlightStart?.catch(() => {});
          await pauseDevice(next.deviceId ?? latest.current.deviceId);
          if (mounted.current && intentEpoch.current === epoch) { latest.current = next; setStatus(next); }
        });
      } else await pauseDevice(device?.id ?? latest.current.deviceId);
    } catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { if (intentEpoch.current === epoch) { actionPending.current = false; if (mounted.current) setPending(false); } }
  }

  async function connectOnly() {
    if (actionPending.current) return;
    actionPending.current = true; setPending(true); setError('');
    try {
      const next = await desktopWorker.connect({ projectRoot: projectRoot.trim(), server: session.server, sessionToken: session.token, backend });
      if (mounted.current) { latest.current = next; setStatus(next); }
    } catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { actionPending.current = false; if (mounted.current) setPending(false); }
  }

  async function saveLimits() {
    if (actionPending.current || !device || !limits || !validLimits) return;
    actionPending.current = true; setPending(true); setError('');
    try {
      const updated = await api.request<Device>(`/devices/${device.id}`, { limits }, 'PATCH');
      if (mounted.current) { acknowledge(updated); setDraft({ id: updated.id, limits: updated.limits, dirty: false }); }
    } catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { actionPending.current = false; if (mounted.current) setPending(false); }
  }

  async function modelAction(action: () => Promise<ModelStatus>) {
    if (modelActionPending.current) return;
    modelActionPending.current = true; setModelPending(true); setError(''); setConfirmDownload(false);
    try { const next = await action(); if (mounted.current) setModel(next); }
    catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { modelActionPending.current = false; if (mounted.current) setModelPending(false); }
    // Download completion never connects or starts contribution.
  }

  const downloading = model?.phase === 'downloading';
  const observed = device ? deviceStatus(device, now) : 'Paused';
  const publicStatus = starting ? 'Starting…' : pending ? 'Updating…' : !initialized ? 'Getting ready…'
    : downloading ? 'Downloading…' : bundled && !model ? 'Checking download…'
    : bundled && model?.phase !== 'ready' ? 'One-time download needed'
    : observed === 'Sharing' ? 'On' : observed === 'Working' ? 'Creating…'
    : observed === 'Paused' ? 'Off' : observed;

  const developerContent = <section className="panel stack developer-worker">
    <h2>Mac image worker</h2>
    <p>{status.message}{status.backend && ` Processor: ${status.backend.toUpperCase()}.`}</p>
    {error && <p className="error" role="alert">{error}</p>}
    {!bundled && <label>GiPU project folder<input value={projectRoot} onChange={event => setProjectRoot(event.target.value)} disabled={pending || active || !initialized} placeholder="/path/to/pocketgrid" spellCheck={false} autoComplete="off" /></label>}
    <label>Processor<select value={backend} onChange={event => setBackend(event.target.value)} disabled={pending || active}><option value="auto">Automatic</option><option value="mps">Apple GPU</option><option value="cpu">CPU</option></select></label>
    <small>{bundled ? 'Connect loads the downloaded model offline; grid access still needs a connection. Weights come from Hugging Face.' : 'Requires a prepared Python environment and cached Tiny-SD model.'}</small>
    <div className="button-row"><button className="secondary" disabled={!initialized || pending || active || (bundled ? model?.phase !== 'ready' || modelPending : !projectRoot.trim())} onClick={() => void connectOnly()}>Connect paused</button><button className="secondary" disabled={!initialized || pending || status.phase === 'stopped'} onClick={() => void turnOff(true)}>Disconnect worker</button></div>
    {device && limits && <div className="stack"><h3>Sharing limits</h3><div className="limits">
      <label>CPU threads<input type="number" min="1" max="8" value={limits.cpu_threads} disabled={pending} onChange={event => editLimits({ cpu_threads: Number(event.target.value) })} /></label>
      <label>Largest image<select value={limits.max_pixels} disabled={pending} onChange={event => editLimits({ max_pixels: Number(event.target.value) })}><option value={65536}>256 × 256</option><option value={147456}>384 × 384</option><option value={262144}>512 × 512</option></select></label>
      <label>Share for<select value={limits.session_minutes} disabled={pending} onChange={event => editLimits({ session_minutes: Number(event.target.value) })}>{[5, 15, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes} minutes</option>)}</select></label>
    </div><small>CPU threads do not limit GPU or memory use. Sharing may continue in the background until expiry. Pause keeps the model loaded; Disconnect releases it.</small><button className="secondary" disabled={pending || !validLimits || !draft?.dirty} onClick={() => void saveLimits()}>Save limits</button></div>}
    {bundled && <small>{model?.message ?? 'Checking model storage…'}</small>}
  </section>;

  return <>
    <div className="generation-contribution stack">
      <ContributionToggle label="Create images" status={publicStatus} checked={starting || pausable} busy={pending || modelPending || downloading} disabled={!initialized || (pending && !starting) || modelPending || downloading || (bundled && !model)} onChange={enabled => { if (enabled) void turnOn(); else void turnOff(); }} />
      {confirmDownload && <div className="download-confirmation stack" role="dialog" aria-labelledby={confirmationId}>
        <h3 id={confirmationId}>Download 1 GB to create images?</h3><p>Download once. Then turn on Create images.</p>
        <div className="button-row"><button ref={confirmButton} disabled={modelPending} onClick={() => void modelAction(() => desktopWorker.downloadModel())}>Download</button><button className="secondary" disabled={modelPending} onClick={() => setConfirmDownload(false)}>Not now</button></div>
      </div>}
      {downloading && <div className="model-download stack"><progress value={Math.min(model.downloadedBytes, model.expectedBytes)} max={model.expectedBytes} aria-label="Model download progress" /><small>{megabytes(model.downloadedBytes)} of about {megabytes(model.expectedBytes)}</small><button className="secondary" disabled={modelPending} onClick={() => void modelAction(() => desktopWorker.cancelModelDownload())}>Cancel download</button></div>}
      {(error || model?.phase === 'failed' || status.phase === 'failed') && <p className="error" role="alert">{model?.phase === 'failed' ? 'Download stopped. Turn on to try again.' : 'Could not update. Try again or check Developer options.'}</p>}
    </div>
    {developerTarget && createPortal(developerContent, developerTarget)}
  </>;
}
