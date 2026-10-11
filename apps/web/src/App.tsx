import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, askNotifications, copyText, errorMessage, isDesktop, notify } from './api';
import { BrowserWorker } from './browserWorker';
import { shouldNotifyEvent } from './eventNotifications';
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
  const [server, setServer] = useState(isDesktop ? 'http://127.0.0.1:8787' : '');
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
  return <main className="onboarding"><div className="brand">◉ PocketGrid <span>prototype</span></div><h1>Let nearby devices<br />do the work.</h1><p>Generate an image on a participating laptop. Export it on another device. See every task and every credit.</p><form onSubmit={submit} className="panel stack"><h2>Join your demo grid</h2><label>Your name<input value={name} onChange={e => setName(e.target.value)} autoComplete="name" placeholder="Alex" maxLength={60} required /></label><label>Grid invite code<input value={code} onChange={e => setCode(e.target.value)} required /></label><label>Coordinator address<input value={server} onChange={e => setServer(e.target.value)} placeholder="Same server as this page" type="text" /><small>{isDesktop ? 'Use your coordinator’s address, including port 8787.' : 'Leave blank for the server hosting this page. On a phone, localhost means the phone.'}</small></label>{error && <p className="error" role="alert">{error}</p>}<button disabled={busy || !name.trim()}>{busy ? 'Joining…' : 'Join grid'}</button><small>Joining does not share your device. This invite-only prototype uses sandbox credits. Grid members can see jobs and images.</small></form></main>;
}

function Dashboard({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const api = useMemo(() => new Api(session.server, session.token), [session.server, session.token]);
  const [state, setState] = useState<Snapshot | null>(null);
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
    const next = await api.request<Snapshot>('/state', undefined, undefined, signal);
    setState(next); setError('');
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
  return <div className="shell"><header><div className="brand">◉ PocketGrid <span>{isDesktop ? 'Mac prototype' : 'prototype'}</span></div><div className="header-actions"><span>{session.name}</span><button className="subtle" onClick={() => { void action('notifications', async () => { const granted = await askNotifications(); notifications.current = granted; setNotifying(granted); if (!granted) throw new Error('Notifications are unavailable or not permitted. Activity still appears below.'); }); }}>{notifying ? 'Notifications on' : 'Enable notifications'}</button><button className="subtle" onClick={onSignOut}>Leave</button></div></header>
    <div className="intro"><div><p className="eyebrow">Your devices. Real work.</p><h1>What should the grid make?</h1><p>Local image generation, shared export work, and a clear receipt.</p></div><div className="balances"><div><strong>{state?.balance ?? '—'}</strong><span>available</span></div><div><strong>{state?.reserved ?? '—'}</strong><span>reserved</span></div><div><strong>{state?.earned ?? '—'}</strong><span>earned</span></div><small>Sandbox credits · no cash value</small></div></div>
    {error && <div className="error banner" role="alert">{error}</div>}
    <div className="main-grid"><section className="panel"><CreateJob api={api} state={state} onCreated={() => refresh()} /></section><section className="panel stack"><div className="section-title"><h2>Share this device</h2><span className={`badge ${localDevice?.enabled ? 'good' : ''}`}>{localDevice?.enabled ? 'Sharing' : 'Paused'}</span></div><p>This window can export images with a verified teal frame. A Python laptop worker runs the image model.</p><label>Device name<input value={deviceName} disabled={!!localId} onChange={e => setDeviceName(e.target.value)} maxLength={80} /></label><LimitsForm value={limits} onChange={setLimits} /><div className="button-row"><button disabled={!!busy} onClick={() => void startLocal()}>{localDevice?.enabled ? 'Apply limits / restart' : 'Start sharing'}</button><button className="secondary" disabled={!!busy || !localDevice?.enabled} onClick={() => void pauseLocal()}>Pause now</button></div><p className="worker-status" role="status">{workerMessage}</p><small>One export at a time. Foreground only. Switching tabs or closing the window pauses sharing. Pixel and time limits are enforced; this is not a CPU percentage cap.</small></section></div>
    <section className="panel"><div className="section-title"><h2>Devices in the grid</h2><span>{state?.devices.filter(device => device.online).length ?? 0} online</span></div><div className="device-grid">{state?.devices.length ? state.devices.map(device => <DeviceCard key={device.id} device={device} own={device.owner_id === state.user.id} local={device.id === localId} busy={!!busy} onUpdate={patch => action(device.id, async () => { if (device.id === localId) { if (patch.enabled === false) { contributionEpoch.current += 1; worker.current?.stop(); setWorkerMessage('Sharing paused.'); } if (patch.enabled === true) { await startLocal(); return; } } await api.request(`/devices/${device.id}`, patch, 'PATCH'); })} />) : <p className="empty">No devices yet. Start sharing here or connect a Python generation worker.</p>}</div><details className="setup"><summary>Connect a laptop that can generate images</summary><p>Run the Python worker from this repository on a laptop with the local model installed. Copy your pairing token below and set <code>POCKETGRID_SESSION_TOKEN</code> when launching the worker to make that laptop controllable from this session. A matching display name alone does not link accounts. See <code>workers/python/README.md</code> for model installation; wait for the model-ready message before your demo.</p><button className="secondary" onClick={() => { void action('pairing', async () => { await copyText(session.token); setPairingCopied(true); }); }}>{pairingCopied ? 'Pairing token copied' : 'Copy worker pairing token'}</button><small>This token grants access to your demo account. Paste it only into your own worker terminal; never share it in a prompt or screenshot.</small><p>Image generation runs on that laptop’s CPU or supported GPU. This desktop window does not bundle the model or start a hidden Python process. Other devices perform image exports.</p><p>Coordinator: <code>{session.server || location.origin}</code></p></details></section>
    <section className="panel"><div className="section-title"><h2>Jobs & results</h2><span>Visible to your demo grid</span></div><div className="jobs">{state?.jobs.length ? state.jobs.map(job => <JobCard key={job.id} api={api} job={job} own={job.owner_id === state.user.id} devices={state.devices} busy={!!busy} onCancel={() => action(job.id, async () => { await api.request(`/jobs/${job.id}/cancel`, {}); })} />) : <p className="empty">Describe an image to start. Jobs wait safely until a capable device is sharing.</p>}</div></section>
    <div className="main-grid"><section className="panel"><h2>Live activity</h2><div className="events" aria-live="polite">{state?.events.length ? state.events.slice(0, 30).map(event => <div className="event" key={event.id}><time>{displayTime(event.created_at)}</time><span>{event.message}</span></div>) : <p className="empty">Task starts, reassignments, and earned credits appear here.</p>}</div></section><section className="panel"><h2>My credit ledger</h2><div className="events">{state?.ledger.length ? state.ledger.slice(0, 30).map(row => <div className="ledger-row" key={row.id}><div><span>{row.note || row.kind.replaceAll('_', ' ')}</span><small>{displayTime(row.created_at)}</small></div><strong className={row.amount > 0 ? 'positive' : ''}>{row.amount > 0 ? '+' : ''}{row.amount}</strong></div>) : <p className="empty">Budget reservations, accepted work, and refunds appear here.</p>}</div></section></div>
    <footer>Invite-only prototype · public demo prompts only · generated images are checked for format, not semantic correctness · no cloud image inference</footer>
  </div>;
}

function LimitsForm({ value, onChange, cpu = false }: { value: Limits; onChange: (limits: Limits) => void; cpu?: boolean }) {
  return <div className="limits">{cpu && <label>CPU threads<input type="number" min="1" max="8" value={value.cpu_threads} onChange={e => onChange({ ...value, cpu_threads: Number(e.target.value) })} /></label>}<label>Largest image<select value={value.max_pixels} onChange={e => onChange({ ...value, max_pixels: Number(e.target.value) })}><option value={65536}>256 × 256</option><option value={147456}>384 × 384</option><option value={262144}>512 × 512</option></select></label><label>Share for<select value={value.session_minutes} onChange={e => onChange({ ...value, session_minutes: Number(e.target.value) })}><option value={5}>5 minutes</option><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={60}>60 minutes</option></select></label></div>;
}

function CreateJob({ api, state, onCreated }: { api: Api; state: Snapshot | null; onCreated: () => Promise<void> }) {
  const [prompt, setPrompt] = useState('A cat riding a tiny bicycle, playful illustration');
  const [count, setCount] = useState(1); const [size, setSize] = useState(256); const [steps, setSteps] = useState(12); const [budget, setBudget] = useState(10); const [agent, setAgent] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const minimum = count * ((state?.pricing.generate ?? 6) + (state?.pricing.finalize ?? 1)) + (state?.pricing.fee ?? 1);
  const pendingRequest = useRef<{ payload: string; id: string } | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    const payload = { prompt: prompt.trim(), count, width: size, height: size, steps, budget, use_agent: agent };
    const serialized = JSON.stringify(payload);
    if (pendingRequest.current?.payload !== serialized) pendingRequest.current = { payload: serialized, id: uniqueId() };
    try { await api.request('/jobs', { ...payload, request_id: pendingRequest.current.id }); pendingRequest.current = null; await onCreated(); } catch (error) { setError(errorMessage(error)); } finally { setBusy(false); }
  }
  return <form className="stack" onSubmit={submit}><h2>Create an image</h2><label>What would you like to see?<textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={3} maxLength={1000} required /></label><div className="limits"><label>Images<select value={count} onChange={e => { const next = Number(e.target.value); setCount(next); setBudget(Math.max(budget, next * 7 + 1)); }}>{[1, 2, 3, 4].map(value => <option key={value}>{value}</option>)}</select></label><label>Size<select value={size} onChange={e => setSize(Number(e.target.value))}>{[256, 384, 512].map(value => <option key={value} value={value}>{value} × {value}</option>)}</select></label><label>Model steps<input type="number" min="4" max="30" value={steps} onChange={e => setSteps(Number(e.target.value))} required /></label></div><label>Maximum budget <span className="muted">(sandbox credits)</span><input type="number" min={minimum} max={state?.balance ?? 100} value={budget} onChange={e => setBudget(Number(e.target.value))} required /></label><small>{minimum} credits quoted: {count * (state?.pricing.generate ?? 6)} generation + {count * (state?.pricing.finalize ?? 1)} export + {state?.pricing.fee ?? 1} service fee. We reserve your budget and return unused credits.</small><label className="check"><input type="checkbox" checked={agent} onChange={e => setAgent(e.target.checked)} disabled={!state?.agent.available} />Plan with AWS Strands{!state?.agent.available && <span className="muted"> (not configured)</span>}</label>{error && <p className="error" role="alert">{error}</p>}<button disabled={busy || !state || !prompt.trim() || budget < minimum || budget > (state?.balance ?? 0)}>{busy ? 'Reserving & submitting…' : `Create · reserve ${budget} credits`}</button><small>Each image is generated on one compatible laptop. Multiple images can use multiple laptops. Phones and browsers do the export step.</small></form>;
}

function DeviceCard({ device, own, local, busy, onUpdate }: { device: Device; own: boolean; local: boolean; busy: boolean; onUpdate: (patch: { enabled?: boolean; limits?: Limits }) => Promise<void> }) {
  const [limits, setLimits] = useState(device.limits);
  const progress = Math.max(0, Math.min(1, device.telemetry.progress ?? 0));
  return <article className="device"><div className="section-title"><h3>{device.name}{local ? ' · this window' : ''}</h3><span className={`dot ${device.online ? 'online' : ''}`} aria-label={device.online ? 'Online' : 'Offline'} /></div><p className="muted">{device.kind} · {device.capabilities.includes('image_generate') ? device.capabilities.includes('image_finalize') ? 'Image generation + export' : 'Image generation' : 'Image export'}</p><div className="device-line"><span>{device.enabled ? device.active_task_id ? 'Working' : 'Available' : 'Paused'}{!device.online ? ' · offline' : ''}</span><strong>{device.earned} earned</strong></div>{device.active_task_id && <><progress value={progress} max="1" /><small>{device.telemetry.stage || 'Processing'} · {Math.round(progress * 100)}%</small></>}<p className="telemetry">{device.telemetry.backend || 'No compute running'}{device.telemetry.rss_mb != null ? ` · ${Math.round(device.telemetry.rss_mb)} MB process memory` : ''}{device.telemetry.cpu_percent != null ? ` · ${device.telemetry.cpu_percent.toFixed(0)}% process CPU` : ''}</p>{device.session_expires_at && device.enabled ? <small>Session ends {displayTime(device.session_expires_at)}</small> : null}{own && <><div className="button-row"><button className="secondary" disabled={busy} onClick={() => void onUpdate({ enabled: !device.enabled })}>{device.enabled ? 'Pause' : 'Start'}</button></div>{!local && <details><summary>Workload limits</summary><LimitsForm value={limits} onChange={setLimits} cpu={device.kind === 'python'} /><button className="secondary" disabled={busy || !Number.isInteger(limits.cpu_threads) || limits.cpu_threads < 1 || limits.cpu_threads > 8} onClick={() => void onUpdate({ limits })}>Save limits</button>{device.kind === 'python' && <small>CPU thread limit does not cap GPU usage. One task runs at a time.</small>}</details>}</>}</article>;
}

function JobCard({ api, job, devices, own, busy, onCancel }: { api: Api; job: Job; devices: Device[]; own: boolean; busy: boolean; onCancel: () => Promise<void> }) {
  const images = job.images.filter(image => image.stage.includes('final') || !job.images.some(other => other.variant === image.variant && other.stage.includes('final')));
  return <article className="job"><div className="section-title"><h3>{job.prompt}</h3><span className={`badge ${job.status === 'completed' ? 'good' : ''}`}>{job.status}</span></div><small>{job.id.slice(0, 8)} · {job.count} image{job.count > 1 ? 's' : ''} · {job.width} × {job.height} · {job.plan.mode}</small><p>{job.plan.explanation}</p><div className="task-list">{job.tasks.map(task => <div key={task.id} className="task"><div><span>{task.kind === 'image_generate' ? 'Generate' : 'Export'} image {task.variant + 1}</span><small>{task.device_id ? devices.find(device => device.id === task.device_id)?.name || 'Assigned device' : 'Waiting for a capable device'}{task.attempts > 1 ? ` · attempt ${task.attempts}` : ''}</small></div><span className="muted">{task.status === 'running' ? `${Math.round((task.progress || 0) * 100)}%` : task.status}</span></div>)}</div>{images.length > 0 && <div className="gallery">{images.map(image => <ImageCard key={image.task_id} api={api} path={image.url} title={`Image ${image.variant + 1}`} stage={image.stage} />)}</div>}{job.receipt ? <div className="receipt"><strong>Receipt</strong><span>Reserved {job.receipt.budget}</span><span>Contributors {job.receipt.contributor_total}</span><span>Service fee {job.receipt.platform_fee}</span><span>Refund {job.receipt.refund}</span><strong>Charged {job.receipt.total_charged}</strong></div> : <p className="muted">Budget {job.budget} · accepted work paid {job.spent} · returned {job.refunded}</p>}{own && ['queued', 'running'].includes(job.status) && <button className="secondary" disabled={busy} onClick={() => void onCancel()}>Cancel & release remaining budget</button>}</article>;
}

function ImageCard({ api, path, title, stage }: { api: Api; path: string; title: string; stage: string }) {
  const [url, setUrl] = useState(''); const [error, setError] = useState('');
  useEffect(() => { const controller = new AbortController(); let objectUrl = ''; setUrl(''); setError(''); void api.image(path, controller.signal).then(blob => { if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); } }).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); }); return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); }; }, [api, path]);
  return <figure>{url ? <a href={url} download={`pocketgrid-${title.replaceAll(' ', '-').toLowerCase()}.png`}><img src={url} alt={`${title}, locally generated`} width="256" height="256" /></a> : <div className="image-placeholder">{error || 'Loading image…'}</div>}<figcaption>{title} · {stage.includes('final') ? 'export verified' : 'awaiting export'}{url && ' · click to save'}</figcaption></figure>;
}
