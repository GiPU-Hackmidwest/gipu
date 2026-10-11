import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, askNotifications, copyText, errorMessage, isDesktop, isMacDesktop, notify } from './api';
import { BrowserWorker } from './browserWorker';
import { GridScene } from './GridScene';
import { DesktopWorkerPanel } from './DesktopWorkerPanel';
import { canPauseDevice, canStartDevice, deviceStatus, isSharing } from './deviceStatus';
import { shouldNotifyEvent } from './eventNotifications';
import { canCancelJob, jobAcknowledgement, jobProgress } from './jobStatus';
import { initialJobSync, mergeJobResponses, reconcileSnapshot, retainJobResponse, snapshotIsCurrent } from './jobSync';
import type { Device, DeviceCredential, Job, Limits, Session, Snapshot } from './types';

const sessionKey = 'pocketgrid.session.v1';
const defaultLimits: Limits = { cpu_threads: 2, max_pixels: 262144, session_minutes: 30 };
function storedSession(): Session | null { try { return JSON.parse(localStorage.getItem(sessionKey) || 'null'); } catch { return null; } }
function displayTime(value: number) { return new Date(value * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
function uniqueId() { return globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`; }

export default function App() {
  const [session, setSession] = useState<Session | null>(storedSession);
  if (!session) return <SignIn onSession={value => { localStorage.setItem(sessionKey, JSON.stringify(value)); setSession(value); }} />;
  return <Dashboard key={`${session.server}:${session.token}`} session={session} onSignOut={() => { localStorage.removeItem(sessionKey); setSession(null); }} />;
}

function SignIn({ onSession }: { onSession: (session: Session) => void }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('pocketgrid-demo');
  const [server, setServer] = useState(isDesktop ? 'https://66-228-53-243.ip.linodeusercontent.com' : '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const normalized = server.trim().replace(/\/$/, '');
      if (normalized && !/^https?:\/\//.test(normalized)) throw new Error('Use an http:// or https:// server address.');
      const result = await new Api(normalized, '').request<{ token: string; user: { name: string } }>('/sessions', { name: name.trim(), join_code: code });
      onSession({ token: result.token, name: result.user.name, server: normalized });
    } catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  }
  return <main className="onboarding"><div className="brand">◉ PocketGrid <span>Device-powered images</span></div><h1><em>Welcome to</em><br />PocketGrid.</h1><p>Make something together.</p><form onSubmit={submit} className="panel stack"><h2>Join your grid</h2><label>Your name<input value={name} onChange={e => setName(e.target.value)} autoComplete="name" placeholder="Alex" maxLength={60} required /></label><label>Grid invite code<input type="password" autoComplete="off" value={code} onChange={e => setCode(e.target.value)} required /></label><details><summary>Grid address</summary><label>Address<input value={server} onChange={e => setServer(e.target.value)} placeholder="Same server as this page" type="text" /><small>{isDesktop ? 'Use the same grid on all your devices.' : 'Leave blank to use this page’s grid.'}</small></label></details>{error && <p className="error" role="alert">{error}</p>}<button disabled={busy || !name.trim()}>{busy ? 'Joining…' : 'Join grid'}</button><small>Sharing stays off until you start. Sandbox credits only.</small></form></main>;
}

function Dashboard({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const api = useMemo(() => new Api(session.server, session.token), [session.server, session.token]);
  const [state, setState] = useState<Snapshot | null>(null);
  const [section, setSection] = useState<'create' | 'contribute' | 'activity'>('create');
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [section]);
  const jobSync = useRef(initialJobSync());
  const refreshSequence = useRef(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [notifying, setNotifying] = useState(false);
  const [pairingCopied, setPairingCopied] = useState(false);
  const [workerMessage, setWorkerMessage] = useState('Sharing is off. Start when you’re ready.');
  const [localId, setLocalId] = useState<string | null>(null);
  const worker = useRef<BrowserWorker | null>(null);
  const contributionEpoch = useRef(0);
  const seen = useRef<Set<string | number> | null>(null);
  const notifications = useRef(false);
  const credentialKey = `pocketgrid.browser.${session.server}.${session.token.slice(0, 12)}`;
  const credential = useRef<DeviceCredential | null>(null);
  const [limits, setLimits] = useState(defaultLimits);
  const [deviceName, setDeviceName] = useState(`${session.name}’s ${isDesktop ? 'desktop window' : 'browser'}`);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const request = { revision: jobSync.current.revision, sequence: ++refreshSequence.current };
    let next: Snapshot;
    try { next = await api.request<Snapshot>('/state', undefined, undefined, signal); }
    catch (error) { if (!snapshotIsCurrent(jobSync.current, request)) return; throw error; }
    const result = reconcileSnapshot(jobSync.current, request, next);
    if (!result) return;
    jobSync.current = result.sync;
    setState(result.snapshot); setError('');
    if (seen.current) {
      for (const event of next.events) if (!seen.current.has(event.id)) {
        seen.current.add(event.id);
        if (notifications.current && shouldNotifyEvent(event, next.user.id)) void notify(event.message).catch(() => {});
      }
    } else seen.current = new Set(next.events.map(event => event.id));
  }, [api]);

  useEffect(() => {
    let stopped = false; let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => { try { await refresh(controller.signal); } catch (error) { if (!stopped) setError(`Coordinator: ${errorMessage(error)}`); } if (!stopped) timer = setTimeout(poll, 2000); };
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [refresh]);

  useEffect(() => {
    try { credential.current = JSON.parse(localStorage.getItem(credentialKey) || 'null'); } catch { credential.current = null; }
    setLocalId(credential.current?.id ?? null);
    // Reloading never resumes contribution without a new explicit Start.
    if (credential.current) void api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH').catch(() => {});
    function pauseForBackground() {
      contributionEpoch.current += 1;
      worker.current?.stop();
      if (credential.current) void api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH', undefined, true).catch(() => {});
      setWorkerMessage('Paused because this window left the foreground. Press Start to share again.');
    }
    const visibility = () => { if (document.hidden) pauseForBackground(); };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pagehide', pauseForBackground);
    return () => {
      document.removeEventListener('visibilitychange', visibility); window.removeEventListener('pagehide', pauseForBackground);
      contributionEpoch.current += 1;
      worker.current?.stop();
      if (credential.current) void api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH', undefined, true).catch(() => {});
    };
  }, [api, credentialKey]);

  function onJobResponse(job: Job) {
    jobSync.current = retainJobResponse(jobSync.current, job);
    const retained = jobSync.current.retained;
    setState(previous => previous ? { ...previous, jobs: mergeJobResponses(previous.jobs, retained) } : previous);
    // The write is already acknowledged. Refresh failure must not become a submit failure.
    void refresh().catch(error => setError(`Request ${job.id.slice(0, 8)} was saved, but live updates are unavailable: ${errorMessage(error)}. You do not need to submit it again.`));
  }
  async function cancelJob(jobId: string) {
    setBusy(jobId); setError('');
    let job: Job;
    try { job = await api.request<Job>(`/jobs/${jobId}/cancel`, {}); }
    catch (error) { setError(errorMessage(error)); return; }
    finally { setBusy(''); }
    onJobResponse(job);
  }
  async function action(label: string, work: () => Promise<void>) { setBusy(label); setError(''); try { await work(); await refresh(); } catch (error) { setError(errorMessage(error)); } finally { setBusy(''); } }
  async function startLocal() {
    const epoch = ++contributionEpoch.current;
    await action('share', async () => {
      if (document.hidden) throw new Error('Bring this window to the foreground first.');
      if (!credential.current) {
        const result = await api.request<{ device: Device; token: string }>('/devices', { name: deviceName.trim() || 'Browser worker', kind: 'browser', capabilities: ['image_finalize'], limits });
        credential.current = { id: result.device.id, token: result.token };
        localStorage.setItem(credentialKey, JSON.stringify(credential.current)); setLocalId(result.device.id);
      }
      if (contributionEpoch.current !== epoch || document.hidden) return;
      await api.request(`/devices/${credential.current.id}`, { enabled: true, limits }, 'PATCH');
      if (contributionEpoch.current !== epoch || document.hidden) {
        await api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH');
        return;
      }
      worker.current?.stop();
      worker.current = new BrowserWorker(api, credential.current, setWorkerMessage); worker.current.start();
    });
  }
  async function pauseLocal() { contributionEpoch.current += 1; await action('share', async () => { worker.current?.stop(); if (credential.current) await api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH'); setWorkerMessage('Sharing paused. Unfinished work can move to another device.'); }); }
  const localDevice = state?.devices.find(device => device.id === localId);
  const localSharing = isSharing(localDevice, state?.server_time ?? NaN);
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark" aria-hidden="true">▦</span> PocketGrid</div>

      <nav aria-label="Main navigation">{(['create', 'contribute', 'activity'] as const).map((item, index) => <button key={item} className={section === item ? 'nav-item selected' : 'nav-item'} aria-current={section === item ? 'page' : undefined} onClick={() => setSection(item)}><span aria-hidden="true">{['✧', '◉', '↗'][index]}</span>{item[0].toUpperCase() + item.slice(1)}</button>)}</nav>
      <div className="grid-identity"><span className="eyebrow">Your grid</span><strong>{session.name}</strong><small>{session.server ? new URL(session.server).host : location.host}</small><span className="connection-state">{error ? 'Updates interrupted' : state ? 'Connected to grid' : 'Connecting…'}</span><button className="subtle" onClick={onSignOut}>Leave grid</button></div>
      <small>Sandbox credits<br />No cash value</small>
    </aside>
    <main className="workspace">
    <header><span>{section === 'create' ? 'Create' : section === 'contribute' ? 'Contribute' : 'Activity'}</span><span className="badge">{state ? `${state.devices.filter(d => d.online).length} devices online` : 'Checking devices…'}</span></header>
    <div className="intro"><div><h1>{section === 'create' ? <><em>Let’s make</em><br />an image.</> : section === 'contribute' ? <><em>Share your</em><br />devices.</> : <><em>Your</em><br />activity.</>}</h1></div><div className="balances"><div><strong>{state?.balance ?? '—'}</strong><span>available</span></div><div><strong>{state?.reserved ?? '—'}</strong><span>reserved</span></div><div><strong>{state?.earned ?? '—'}</strong><span>earned</span></div><small>Sandbox credits · no cash value</small></div></div>
    {error && <div className="error banner" role="alert">{error}</div>}
    <div hidden={section !== 'create'}><div className="create-layout"><section className="panel compose-panel"><CreateJob api={api} state={state} onCreated={onJobResponse} /></section><GridScene state={state} onOpen={() => setSection('contribute')} /></div></div>
    <div hidden={section !== 'contribute'}><section className="panel">{isMacDesktop && <DesktopWorkerPanel session={session} api={api} devices={state?.devices ?? []} now={state?.server_time ?? NaN} />}<div className="section-title"><h2>{isMacDesktop ? 'Finish images in this window' : 'Share this device'}</h2><span className="badge">Foreground only</span></div><div className="stack"><div className="section-title"><h3>Image finishing</h3><span className={`badge ${localSharing ? 'good' : ''}`}>{deviceStatus(localDevice, state?.server_time ?? NaN)}</span></div><p>Help finish images. Keep this window open.</p><label>Device name<input value={deviceName} disabled={!!localId} onChange={e => setDeviceName(e.target.value)} maxLength={80} /></label><LimitsForm value={limits} onChange={setLimits} /><div className="button-row"><button disabled={!!busy} onClick={() => void startLocal()}>{localSharing ? 'Apply limits / restart' : 'Start sharing'}</button><button className="secondary" disabled={!!busy || !localDevice?.enabled} onClick={() => void pauseLocal()}>Pause now</button></div><p className="worker-status" role="status">{workerMessage}</p><details><summary>How sharing works</summary><p>This window adds the verified four-pixel frame. Hiding or closing it pauses sharing. Image size and session limits apply; these are not CPU, GPU, or memory caps.</p></details></div></section>
    <section className="panel"><div className="section-title"><h2>Devices in the grid</h2><span>{state?.devices.filter(device => device.online).length ?? 0} online</span></div><div className="device-grid">{state?.devices.length ? state.devices.map(device => <DeviceCard key={device.id} device={device} now={state.server_time} own={device.owner_id === state.user.id} local={device.id === localId} busy={!!busy} onUpdate={patch => action(device.id, async () => { if (device.id === localId) { if (patch.enabled === false) { contributionEpoch.current += 1; worker.current?.stop(); setWorkerMessage('Sharing paused.'); } if (patch.enabled === true) { await startLocal(); return; } } await api.request(`/devices/${device.id}`, patch, 'PATCH'); })} />) : <p className="empty">No devices yet. Start sharing here or connect a Python generation worker.</p>}</div><details className="setup"><summary>Advanced · manual worker pairing</summary><p>Run the Python worker from this repository on a laptop with the local model installed. Copy your pairing token below and set <code>POCKETGRID_SESSION_TOKEN</code> when launching the worker to make that laptop controllable from this session. A matching display name alone does not link accounts. See <code>workers/python/README.md</code> for model installation; wait for the model-ready message before your demo.</p><button className="secondary" onClick={() => { void action('pairing', async () => { await copyText(session.token); setPairingCopied(true); }); }}>{pairingCopied ? 'Pairing token copied' : 'Copy worker pairing token'}</button><small>This token grants access to your demo account. Paste it only into your own worker terminal; never share it in a prompt or screenshot.</small><p>Image generation runs on that laptop’s CPU or supported GPU. The Mac app can connect an already-installed worker using the explicit action above. The model is not bundled with this interface. Other devices perform image exports.</p><p>Coordinator: <code>{session.server || location.origin}</code></p></details></section></div>
    <section hidden={section !== 'create'} className="panel"><div className="section-title"><h2>Your requests & results</h2><span>Shared with grid members</span></div><div className="jobs">{state?.jobs.some(job => job.owner_id === state.user.id) ? state.jobs.filter(job => job.owner_id === state.user.id).map(job => <JobCard key={job.id} api={api} job={job} own={job.owner_id === state.user.id} devices={state.devices} now={state.server_time} canStartExport={!localSharing && limits.max_pixels >= job.width * job.height} onStartExport={startLocal} busy={!!busy} onCancel={() => cancelJob(job.id)} />) : <p className="empty">Describe an image to start. Jobs wait safely until a capable device is sharing.</p>}</div></section>
    <div hidden={section !== 'activity'}><section className="panel section-title"><div><h2>Stay in the loop</h2><p>Activity is always available here.</p></div><button className="secondary" onClick={() => { void action('notifications', async () => { const granted = await askNotifications(); notifications.current = granted; setNotifying(granted); if (!granted) throw new Error('Notifications are unavailable or not permitted. Activity still appears here.'); }); }}>{notifying ? 'Notifications on' : 'Enable notifications'}</button></section><div className="main-grid"><section className="panel"><h2>Live activity</h2><div className="events" aria-live="polite">{state?.events.length ? state.events.slice(0, 30).map(event => <div className="event" key={event.id}><time>{displayTime(event.created_at)}</time><span>{event.message}</span></div>) : <p className="empty">Task starts, reassignments, and earned credits appear here.</p>}</div></section><section className="panel"><h2>My credit ledger</h2><div className="events">{state?.ledger.length ? state.ledger.slice(0, 30).map(row => <div className="ledger-row" key={row.id}><div><span>{row.note || row.kind.replaceAll('_', ' ')}</span><small>{displayTime(row.created_at)}</small></div><strong className={row.amount > 0 ? 'positive' : ''}>{row.amount > 0 ? '+' : ''}{row.amount}</strong></div>) : <p className="empty">Budget reservations, accepted work, and refunds appear here.</p>}</div></section></div></div>
    <footer><details><summary>About this grid</summary><p>Invite-only demo. Grid members can see prompts and images. Credits have no cash value. Laptops generate images locally; phones and browsers add a verified four-pixel frame. Generated images are checked for format, not accuracy.</p></details></footer>
  </main></div>;
}

function LimitsForm({ value, onChange, cpu = false }: { value: Limits; onChange: (limits: Limits) => void; cpu?: boolean }) {
  return <div className="limits">{cpu && <label>CPU threads<input type="number" min="1" max="8" value={value.cpu_threads} onChange={e => onChange({ ...value, cpu_threads: Number(e.target.value) })} /></label>}<label>Largest image<select value={value.max_pixels} onChange={e => onChange({ ...value, max_pixels: Number(e.target.value) })}><option value={65536}>256 × 256</option><option value={147456}>384 × 384</option><option value={262144}>512 × 512</option></select></label><label>Share for<select value={value.session_minutes} onChange={e => onChange({ ...value, session_minutes: Number(e.target.value) })}><option value={5}>5 minutes</option><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={60}>60 minutes</option></select></label></div>;
}

function CreateJob({ api, state, onCreated }: { api: Api; state: Snapshot | null; onCreated: (job: Job) => void }) {
  const [prompt, setPrompt] = useState('A cat riding a tiny bicycle, playful illustration');
  const [count, setCount] = useState(1); const [size, setSize] = useState(256); const [steps, setSteps] = useState(12); const [budget, setBudget] = useState(10); const [agent, setAgent] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const minimum = count * ((state?.pricing.generate ?? 6) + (state?.pricing.finalize ?? 1)) + (state?.pricing.fee ?? 1);
  const pendingRequest = useRef<{ payload: string; id: string } | null>(null);
  const submitting = useRef(false);
  const [accepted, setAccepted] = useState<Job | null>(null);
  const acceptedJob = state?.jobs.find(job => job.id === accepted?.id) ?? accepted;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setError(''); setAccepted(null);
    const payload = { prompt: prompt.trim(), count, width: size, height: size, steps, budget, use_agent: agent };
    const serialized = JSON.stringify(payload);
    if (pendingRequest.current?.payload !== serialized) pendingRequest.current = { payload: serialized, id: uniqueId() };
    let job: Job;
    try { job = await api.request<Job>('/jobs', { ...payload, request_id: pendingRequest.current.id }); }
    catch (error) { setError(errorMessage(error)); return; }
    finally { submitting.current = false; setBusy(false); }
    pendingRequest.current = null; setAccepted(job);
    onCreated(job);
  }
  return <form className="stack" onSubmit={submit}><h2>Your prompt</h2><label>Describe your image<textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={3} maxLength={1000} required /></label><small>{minimum} credits estimated · {state?.balance ?? '—'} available</small><details><summary>Options</summary><div className="stack"><div className="limits"><label>Images<select value={count} onChange={e => { const next = Number(e.target.value); setCount(next); setBudget(Math.max(budget, next * ((state?.pricing.generate ?? 6) + (state?.pricing.finalize ?? 1)) + (state?.pricing.fee ?? 1))); }}>{[1, 2, 3, 4].map(value => <option key={value}>{value}</option>)}</select></label><label>Size<select value={size} onChange={e => setSize(Number(e.target.value))}>{[256, 384, 512].map(value => <option key={value} value={value}>{value} × {value}</option>)}</select></label></div><label>Maximum budget <span className="muted">(sandbox credits)</span><input type="number" min={minimum} max={state?.balance ?? 100} value={budget} onChange={e => setBudget(Number(e.target.value))} required /></label><label>Model steps<input type="number" min="4" max="30" value={steps} onChange={e => setSteps(Number(e.target.value))} required /></label><small>{count * (state?.pricing.generate ?? 6)} generation + {count * (state?.pricing.finalize ?? 1)} finishing + {state?.pricing.fee ?? 1} service fee.</small><label className="check"><input type="checkbox" checked={agent} onChange={e => setAgent(e.target.checked)} disabled={!state?.agent.available} />Let the planner choose devices{!state?.agent.available && <span className="muted"> (not configured)</span>}</label><small>{agent ? 'AWS Strands plans with the configured chat model. A laptop still generates your image.' : 'Direct queue · available compatible devices accept the work.'}</small></div></details>{acceptedJob && <p className="worker-status" role="status">{jobAcknowledgement(acceptedJob)}</p>}{error && <p className="error" role="alert">{error}</p>}<button disabled={busy || !state || !prompt.trim() || budget < minimum || budget > (state?.balance ?? 0)}>{busy ? 'Submitting request…' : 'Create image'}</button><small>Reserves {budget} credits. Unused credits return.</small></form>;
}

function DeviceCard({ device, now, own, local, busy, onUpdate }: { device: Device; now: number; own: boolean; local: boolean; busy: boolean; onUpdate: (patch: { enabled?: boolean; limits?: Limits }) => Promise<void> }) {
  const [limits, setLimits] = useState(device.limits);
  const progress = Math.max(0, Math.min(1, device.telemetry.progress ?? 0));
  const sharing = isSharing(device, now);
  const pausable = canPauseDevice(device, now);
  return <article className="device"><div className="section-title"><h3>{device.name}{local ? ' · this window' : ''}</h3><span className={`dot ${device.online ? 'online' : ''}`} aria-label={device.online ? 'Online' : 'Offline'} /></div><p className="muted">{device.kind} · {device.capabilities.includes('image_generate') ? device.capabilities.includes('image_finalize') ? 'Image generation + export' : 'Image generation' : 'Image export'}</p><div className="device-line"><span>{deviceStatus(device, now)}</span><strong>{device.earned} earned</strong></div>{sharing && device.active_task_id && <><progress value={progress} max="1" aria-label="Current image progress" /><small>{device.telemetry.stage || 'Processing'} · {Math.round(progress * 100)}%</small></>}<details><summary>Measured usage</summary><p className="telemetry" aria-label="Measured resource use">{device.telemetry.backend || 'No compute running'}{device.telemetry.rss_mb != null ? ` · ${Math.round(device.telemetry.rss_mb)} MB process memory` : ''}{device.telemetry.cpu_percent != null ? ` · ${device.telemetry.cpu_percent.toFixed(0)}% process CPU` : ''}</p></details>{device.session_expires_at && sharing ? <small>Session ends {displayTime(device.session_expires_at)}</small> : null}{own && <><div className="button-row"><button className="secondary" disabled={busy || (!pausable && !canStartDevice(device, local))} onClick={() => void onUpdate({ enabled: !pausable })}>{pausable ? 'Pause' : 'Start sharing'}</button></div>{!local && <details><summary>Workload limits</summary><LimitsForm value={limits} onChange={setLimits} cpu={device.kind === 'python'} /><button className="secondary" disabled={busy || !Number.isInteger(limits.cpu_threads) || limits.cpu_threads < 1 || limits.cpu_threads > 8} onClick={() => void onUpdate({ limits })}>Save limits</button>{device.kind === 'python' && <small>CPU thread limit does not cap GPU usage. One task runs at a time.</small>}</details>}</>}</article>;
}

function JobCard({ api, job, devices, now, canStartExport, onStartExport, own, busy, onCancel }: { api: Api; job: Job; devices: Device[]; now: number; canStartExport: boolean; onStartExport: () => Promise<void>; own: boolean; busy: boolean; onCancel: () => Promise<void> }) {
  const images = job.images.filter(image => image.stage.includes('final') || !job.images.some(other => other.variant === image.variant && other.stage.includes('final')));
  const progress = jobProgress(job, devices, now);
  return <article className="job">
    <div className="section-title"><h3>{job.prompt}</h3><span className={`badge ${job.status === 'completed' ? 'good' : ''}`}>{job.status}</span></div>
    <div className="job-progress">
      <strong>{progress.title}</strong>{job.status !== 'completed' && <p>{progress.detail}</p>}
      {job.status !== 'planning' && job.status !== 'completed' && <><progress value={progress.completed} max={progress.total} aria-label="Completed generation and export steps" /><small>{progress.generated}/{job.count} generated · {progress.finalized}/{job.count} exports verified</small></>}
      {progress.waitingForExport && canStartExport && <><button className="secondary" disabled={busy} onClick={() => void onStartExport()}>Start this window to finish images</button><small>Uses your limits in Contribute. Keep this window visible; pause anytime in Contribute.</small></>}
    </div>

    {images.length > 0 && <div className="gallery">{images.map(image => <ImageCard key={image.task_id} api={api} path={image.url} title={`Image ${image.variant + 1}`} stage={image.stage} />)}</div>}
    <details><summary>Plan details</summary><p>{job.plan.explanation}</p></details>
    <details><summary>Devices & steps</summary><div className="task-list">{job.tasks.map(task => <div key={task.id} className="task"><div><span>{task.kind === 'image_generate' ? 'Generate' : 'Export'} image {task.variant + 1}</span><small>{task.device_id ? devices.find(device => device.id === task.device_id)?.name || 'Assigned device' : task.status === 'queued' ? 'Awaiting assignment' : 'No active assignment'}{task.attempts > 1 ? ` · attempt ${task.attempts}` : ''}</small></div><span className="muted">{task.status === 'running' ? `${Math.round((task.progress || 0) * 100)}%` : task.status}</span></div>)}</div></details>

    {job.receipt ? <details className="receipt-details"><summary>Receipt · {job.receipt.total_charged} credits</summary><div className="receipt"><span>Reserved {job.receipt.budget}</span><span>Contributors {job.receipt.contributor_total}</span><span>Service fee {job.receipt.platform_fee}</span><span>Refund {job.receipt.refund}</span><strong>Charged {job.receipt.total_charged}</strong></div></details> : <p className="muted">Budget {job.budget} · still reserved {job.reserved} · accepted work paid {job.spent} · returned {job.refunded}</p>}
    {own && canCancelJob(job) && <button className="secondary" disabled={busy} onClick={() => void onCancel()}>Cancel request</button>}
  </article>;
}

function ImageCard({ api, path, title, stage }: { api: Api; path: string; title: string; stage: string }) {
  const [url, setUrl] = useState(''); const [error, setError] = useState('');
  const [saveMessage, setSaveMessage] = useState('');
  const [saveReady, setSaveReady] = useState(!isMacDesktop);
  useEffect(() => {
    if (!isMacDesktop || !url) return;
    let disposed = false; let unlisten: (() => void) | undefined;
    setSaveReady(false); setSaveMessage('');
    void import('@tauri-apps/api/event').then(({ listen }) => listen<{ url: string; success: boolean }>('image-download-finished', ({ payload }) => {
      if (payload.url === url) setSaveMessage(payload.success ? 'Saved to Downloads' : 'Could not save. Try again.');
    })).then(stop => { if (disposed) stop(); else { unlisten = stop; setSaveReady(true); } }).catch(() => { if (!disposed) setSaveMessage('Saving is unavailable.'); });
    return () => { disposed = true; unlisten?.(); };
  }, [url]);
  useEffect(() => { const controller = new AbortController(); let objectUrl = ''; setUrl(''); setError(''); void api.image(path, controller.signal).then(blob => { if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); } }).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); }); return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); }; }, [api, path]);
  return <figure>{url ? <a href={url} onClick={event => { if (!saveReady) { event.preventDefault(); return; } if (isMacDesktop) setSaveMessage('Saving…'); }} aria-label={`Save ${title}`} download={`pocketgrid-${title.replaceAll(' ', '-').toLowerCase()}.png`}><img src={url} alt={`${title}, locally generated`} width="256" height="256" /></a> : <div className="image-placeholder">{error || 'Loading image…'}</div>}<figcaption>{title} · {stage.includes('final') ? 'Ready' : 'Preview'}{url && ' · Save image'}</figcaption>{saveMessage && <small role="status">{saveMessage}</small>}</figure>;
}
