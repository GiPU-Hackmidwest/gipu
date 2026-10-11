import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { createPortal } from 'react-dom';
import { Brand } from './Brand';
import { SignInScreen } from './SignInScreen';
import { AccountPage } from './AccountPage';
import { sessionStore } from './sessionStorage';
import { signOut } from './identity';
import { shouldRecoverSession, stopAndSignOut } from './accountLifecycle';
import { activityLabel, creditLabel, gridCounts, imageLabel, privateSnapshot, visibleImages } from './publicPresentation';
import { ContributionToggle } from './ContributionToggle';
import { Api, ApiError, askNotifications, copyText, errorMessage, isAndroidApp, isDesktop, isMacDesktop, isMobileApp, notify } from './api';
import { BrowserWorker } from './browserWorker';
import { GridScene } from './GridScene';
import { DesktopWorkerPanel } from './DesktopWorkerPanel';
import { canPauseDevice, canStartDevice, deviceStatus, isSharing } from './deviceStatus';
import { shouldNotifyEvent } from './eventNotifications';
import { canCancelJob, jobAcknowledgement, jobProgress } from './jobStatus';
import { initialJobSync, mergeJobResponses, reconcileSnapshot, retainJobResponse, snapshotIsCurrent } from './jobSync';
import type { Device, DeviceCredential, GridLink, Job, Limits, Session, Snapshot } from './types';

const developerKey = 'pocketgrid.developer-options';
function storedDeveloperOptions() { try { return localStorage.getItem(developerKey) === 'true'; } catch { return false; } }
const defaultLimits: Limits = { cpu_threads: 2, max_pixels: 262144, session_minutes: 30 };
function displayTime(value: number) { return new Date(value * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
function uniqueId() { return globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`; }

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [incomingLink, setIncomingLink] = useState<GridLink | null>(null);
  const [linkError, setLinkError] = useState('');
  useEffect(() => {
    if (!isAndroidApp) return;
    let disposed = false; let unlisten: (() => void) | undefined;
    void import('./android').then(module => module.androidAdapters()).then(adapters => {
      if (disposed) return;
      return adapters.listenForGridLinks(link => { if (!disposed) { setIncomingLink(link); setLinkError(''); } });
    }).then(stop => { if (disposed) stop?.(); else unlisten = stop; })
      .catch(() => { if (!disposed) setLinkError('Could not open the link. You can paste it instead.'); });
    return () => { disposed = true; unlisten?.(); };
  }, []);
  useEffect(() => {
    let disposed = false; setLoading(true); setError('');
    void Promise.resolve().then(() => sessionStore().load()).then(value => { if (!disposed) setSession(value); })
      .catch(() => { if (!disposed) setError('Could not open your saved account. Try again.'); })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [attempt]);
  if (loading || error) return <main className="onboarding"><Brand /><section className="panel stack">{error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(value => value + 1)}>Try again</button></> : <p role="status">Opening your account…</p>}</section></main>;
  if (!session) return <SignInScreen incomingLink={incomingLink} linkError={linkError} onDismissLink={() => setIncomingLink(null)} onSession={async value => { await sessionStore().save(value); setIncomingLink(null); setLinkError(''); setSession(value); }} />;
  return <Dashboard key={`${session.server}:${session.token}`} session={session} incomingLink={incomingLink} linkError={linkError} onDismissLink={() => setIncomingLink(null)} onSignOut={async () => { await sessionStore().clear(); setSession(null); }} />;
}

function Dashboard({ session, onSignOut, incomingLink, onDismissLink, linkError }: { session: Session; onSignOut: () => Promise<void>; incomingLink: GridLink | null; onDismissLink: () => void; linkError: string }) {
  const api = useMemo(() => new Api(session.server, session.token), [session.server, session.token]);
  const incomingPrompt = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!incomingLink || !incomingPrompt.current) return;
    const previous = document.activeElement;
    incomingPrompt.current.focus({ preventScroll: true });
    incomingPrompt.current.scrollIntoView({ block: 'center', behavior: 'instant' });
    return () => { if (previous instanceof HTMLElement && previous.isConnected) previous.focus({ preventScroll: true }); };
  }, [incomingLink]);
  const [state, setState] = useState<Snapshot | null>(null);
  const [section, setSection] = useState<'create' | 'contribute' | 'activity' | 'developer' | 'account'>('create');
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [section]);
  const [developerEnabled, setDeveloperEnabled] = useState(storedDeveloperOptions);
  const [developerTarget, setDeveloperTarget] = useState<HTMLDivElement | null>(null);
  const [requestTarget, setRequestTarget] = useState<HTMLDivElement | null>(null);
  function changeDeveloperOptions(enabled: boolean) {
    setDeveloperEnabled(enabled);
    try { localStorage.setItem(developerKey, String(enabled)); } catch { /* Usable for this session without storage. */ }
  }
  useEffect(() => {
    const settingsShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === ',') { event.preventDefault(); setSection('developer'); }
    };
    window.addEventListener('keydown', settingsShortcut);
    return () => window.removeEventListener('keydown', settingsShortcut);
  }, []);
  const localActionPending = useRef(false);
  const localOperation = useRef<Promise<void> | null>(null);
  const stopManaged = useRef<(() => Promise<void>) | null>(null);
  const registerManagedStop = useCallback((stop: (() => Promise<void>) | null) => { stopManaged.current = stop; }, []);
  const leavingRef = useRef(false);
  const dashboardMounted = useRef(false);
  useEffect(() => { dashboardMounted.current = true; return () => { dashboardMounted.current = false; }; }, []);
  const expiredRef = useRef(false);
  const [expired, setExpired] = useState(false);
  const recoverSession = useRef<() => Promise<void>>(async () => {});
  const [leaving, setLeaving] = useState(false);
  const recoveryPrompt = useRef<HTMLElement>(null);
  useEffect(() => {
    if (expired && !leaving && recoveryPrompt.current) {
      recoveryPrompt.current.focus({ preventScroll: true });
      recoveryPrompt.current.scrollIntoView({ block: 'center', behavior: 'instant' });
    }
  }, [expired, leaving]);
  const [leaveError, setLeaveError] = useState('');
  const jobSync = useRef(initialJobSync());
  const refreshSequence = useRef(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [notifying, setNotifying] = useState(false);
  const [pairingCopied, setPairingCopied] = useState(false);
  const [workerMessage, setWorkerMessage] = useState('Sharing is off. Start when you’re ready.');
  const [localId, setLocalId] = useState<string | null>(null);
  const [managedId, setManagedId] = useState<string | null>(null);
  const worker = useRef<BrowserWorker | null>(null);
  const contributionEpoch = useRef(0);
  const seen = useRef<Set<string | number> | null>(null);
  const notifications = useRef(false);
  const credentialKey = `pocketgrid.browser.${session.server}.${session.token.slice(0, 12)}`;
  const credential = useRef<DeviceCredential | null>(null);
  const [limits, setLimits] = useState(defaultLimits);
  const [deviceName, setDeviceName] = useState(`${session.name}’s ${isDesktop ? 'desktop window' : isMobileApp ? 'phone app' : 'browser'}`);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const request = { revision: jobSync.current.revision, sequence: ++refreshSequence.current };
    let next: Snapshot;
    try { next = privateSnapshot(await api.request<Snapshot>('/state', undefined, undefined, signal)); }
    catch (error) {
      const current = snapshotIsCurrent(jobSync.current, request);
      if (shouldRecoverSession(error instanceof ApiError ? error.status : undefined, {
        mounted: dashboardMounted.current, current, expired: expiredRef.current, leaving: leavingRef.current,
      })) {
        expiredRef.current = true; setExpired(true);
        // Keep the controller mounted until every local worker is fenced and storage is cleared.
        void recoverSession.current();
      }
      if (!current) return;
      throw error;
    }
    const result = reconcileSnapshot(jobSync.current, request, next);
    if (!result) return;
    jobSync.current = result.sync;
    setState(result.snapshot); setError('');
    if (seen.current) {
      for (const event of next.events) if (!seen.current.has(event.id)) {
        seen.current.add(event.id);
        if (notifications.current && shouldNotifyEvent(event, next.user.id, new Set(next.jobs.map(job => job.id)))) void notify(activityLabel(event)).catch(() => {});
      }
    } else seen.current = new Set(next.events.map(event => event.id));
  }, [api]);

  useEffect(() => {
    let stopped = false; let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => { try { await refresh(controller.signal); } catch (error) { if (!stopped) setError(`Coordinator: ${errorMessage(error)}`); } if (!stopped && !expiredRef.current) timer = setTimeout(poll, 2000); };
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
    if (localActionPending.current || leavingRef.current) return;
    localActionPending.current = true;
    const epoch = ++contributionEpoch.current;
    const operation = (async () => {
      const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 12000);
      try {
      if (document.hidden) throw new Error('Bring this window to the foreground first.');
      if (!credential.current) {
        const result = await api.request<{ device: Device; token: string }>('/devices', { name: deviceName.trim() || 'Browser worker', kind: 'browser', capabilities: ['image_finalize'], limits }, undefined, controller.signal);
        credential.current = { id: result.device.id, token: result.token };
        localStorage.setItem(credentialKey, JSON.stringify(credential.current)); setLocalId(result.device.id);
      }
      if (contributionEpoch.current !== epoch || document.hidden) return;
      await api.request(`/devices/${credential.current.id}`, { enabled: true, limits }, 'PATCH', controller.signal);
      if (contributionEpoch.current !== epoch || document.hidden) {
        await api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH', controller.signal);
        return;
      }
      worker.current?.stop();
      worker.current = new BrowserWorker(api, credential.current, setWorkerMessage); worker.current.start();
      } finally { clearTimeout(timeout); }
    })();
    localOperation.current = operation;
    try { await action('share', () => operation); } finally { if (localOperation.current === operation) localOperation.current = null; localActionPending.current = false; }
  }
  async function pauseLocal() { contributionEpoch.current += 1; await action('share', async () => { worker.current?.stop(); if (credential.current) await api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH'); setWorkerMessage('Sharing paused. Unfinished work can move to another device.'); }); }
  async function leaveAccount() {
    if (leavingRef.current) return;
    leavingRef.current = true; setLeaving(true); setLeaveError('');
    contributionEpoch.current += 1; worker.current?.stop();
    try {
      await stopAndSignOut({
        legacy: !!state && state.grid === undefined,
        stops: [
          async () => {
            // Drain any late enable before revoking its credential.
            await localOperation.current?.catch(() => {});
            if (credential.current) {
              const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 4000);
              try { await api.request(`/devices/${credential.current.id}`, { enabled: false }, 'PATCH', controller.signal); }
              finally { clearTimeout(timeout); }
            }
          },
          async () => {
            if (isMacDesktop) {
              if (!stopManaged.current) throw new Error('Image worker is getting ready.');
              await stopManaged.current();
            }
          },
        ],
        revoke: () => signOut(api), clear: onSignOut,
      });
    } catch { setLeaveError('Could not finish signing out. Try again.'); }
    finally { leavingRef.current = false; setLeaving(false); }
  }
  recoverSession.current = leaveAccount;
  const localDevice = state?.devices.find(device => device.id === localId);
  const localSharing = isSharing(localDevice, state?.server_time ?? NaN);
  const titles = { create: 'Create', contribute: 'Contribute', activity: 'Activity', developer: 'Developer options', account: 'Account' };
  return <>{leaving && <p className="signout-status" role="status">Signing out…</p>}{expired && !leaving && <section ref={recoveryPrompt} tabIndex={-1} className="panel stack" aria-label="Sign in again"><p role="alert">Sign-in expired.</p>{leaveError && <p role="alert">{leaveError}</p>}<button onClick={() => void leaveAccount()}>Return to sign in</button></section>}<div className="shell" inert={leaving || expired}>
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Main navigation">{(['create', 'contribute', 'activity'] as const).map(item => <button key={item} className={section === item ? 'nav-item selected' : 'nav-item'} aria-current={section === item ? 'page' : undefined} onClick={() => setSection(item)}><NavIcon name={item} />{titles[item]}</button>)}</nav>
      <button className={`nav-item developer-link ${section === 'developer' ? 'selected' : ''}`} aria-current={section === 'developer' ? 'page' : undefined} onClick={() => setSection('developer')}><NavIcon name="developer" />Developer options</button>
      <div className="grid-identity"><span className="account-avatar" aria-hidden="true">{session.name.slice(0, 1).toUpperCase()}</span><div><strong>{session.name}</strong><span className="connection-state">{error ? 'Updates interrupted' : state ? 'Connected' : 'Connecting…'}</span></div><button className="subtle" aria-current={section === 'account' ? 'page' : undefined} onClick={() => setSection('account')}>Account</button></div>
      <small>Sandbox credits · no cash value</small>
    </aside>
    <main className="workspace">
      <header><span>YOUR WORKSPACE</span><span className="badge">{gridCounts(state) ? `${gridCounts(state)!.connected} connected` : state ? 'Grid count unavailable' : 'Connecting…'}</span></header>
      <div className="intro"><h1>{titles[section]}</h1>{section !== 'developer' && section !== 'account' && <div className="balances"><div><strong>{state?.balance ?? '—'}</strong><span>available</span></div><div><strong>{state?.reserved ?? '—'}</strong><span>reserved</span></div><div><strong>{state?.earned ?? '—'}</strong><span>earned</span></div></div>}</div>
      {incomingLink && <section ref={incomingPrompt} tabIndex={-1} className="panel stack" aria-label="Switch account"><h2>Use this link?</h2><p className="grid-address">{incomingLink.server}</p><p>Signs out of this account on this device.</p><small>Keep access with a linked device or login.</small><div className="button-row"><button disabled={leaving} onClick={() => void leaveAccount()}>Sign out and continue</button><button className="secondary" disabled={leaving} onClick={onDismissLink}>Cancel</button></div></section>}
      {linkError && <p className="error" role="alert">{linkError}</p>}
      {error && <div className="error banner" role="alert">{error}</div>}{leaveError && <div className="error banner" role="alert">{leaveError}</div>}{section === 'account' && <AccountPage api={api} session={session} username={state?.user.username} supported={state ? state.grid !== undefined : undefined} serverTime={state?.server_time} leaving={leaving} onLeave={leaveAccount} />}
      <div hidden={section !== 'create'}><div className="create-layout"><section className="panel compose-panel"><CreateJob api={api} state={state} onCreated={onJobResponse} developerTarget={requestTarget} /></section><GridScene state={state} onOpen={() => setSection('contribute')} /></div></div>
      <div hidden={section !== 'contribute'}>
        <div className={`contribution-layout ${isMacDesktop ? 'with-generation' : ''}`}>
          {isMacDesktop && <section className="panel contribution-card"><div className="contribution-art" aria-hidden="true"><span><svg viewBox="0 0 32 32"><rect x="5" y="5" width="22" height="16" rx="3"/><path d="M2 25h28M12 12h8M16 8v8"/></svg></span></div><DesktopWorkerPanel session={session} api={api} devices={state?.devices ?? []} now={state?.server_time ?? NaN} onDeviceIdChange={setManagedId} developerTarget={developerTarget} onStopReady={registerManagedStop} /></section>}
          <section className="panel contribution-card finish-card">
            <div className="contribution-art finishing-art" aria-hidden="true"><span><svg viewBox="0 0 32 32"><rect x="6" y="3" width="20" height="26" rx="4"/><path d="m11 16 4 4 7-8"/></svg></span></div>
            <ContributionToggle label="Finish images" status={deviceStatus(localDevice, state?.server_time ?? NaN)} checked={!!localDevice && canPauseDevice(localDevice, state?.server_time ?? NaN)} busy={busy === 'share'} disabled={!!busy || !state} onChange={enabled => { void (enabled ? startLocal() : pauseLocal()); }} />
            <p>Keep this {isMobileApp ? 'app' : 'window'} open while sharing.</p>
            {localSharing && localDevice?.session_expires_at && <small>Until {displayTime(localDevice.session_expires_at)}</small>}
          </section>
        </div>
        <div className="contribute-note"><span className="status-pin" aria-hidden="true" /><p>You choose when to share. Switch off to pause.</p></div>
      </div>
      <section hidden={section !== 'create'} className="panel"><div className="section-title"><h2>Your images</h2></div><div className="jobs">{state?.jobs.some(job => job.owner_id === state.user.id) ? state.jobs.filter(job => job.owner_id === state.user.id).map(job => <JobCard key={job.id} api={api} job={job} own={true} devices={state.devices} now={state.server_time} canStartExport={!localSharing && limits.max_pixels >= job.width * job.height} onStartExport={startLocal} busy={!!busy} onCancel={() => cancelJob(job.id)} />) : <p className="empty">Your next image starts with a prompt.</p>}</div></section>
      <div hidden={section !== 'activity'}><section className="panel section-title"><div><h2>Notifications</h2><p>Know when your image is ready.</p></div><button className="secondary" onClick={() => { void action('notifications', async () => { const granted = await askNotifications(); notifications.current = granted; setNotifying(granted); if (!granted) throw new Error('Notifications are unavailable or not permitted. Activity still appears here.'); }); }}>{notifying ? 'Notifications on' : 'Enable notifications'}</button></section><div className="main-grid"><section className="panel"><h2>Recent activity</h2><div className="events" aria-live="polite">{state?.events.length ? state.events.slice(0, 30).map(event => <div className="event" key={event.id}><time>{displayTime(event.created_at)}</time><span>{activityLabel(event)}</span></div>) : <p className="empty">Your activity will appear here.</p>}</div></section><section className="panel"><h2>Your credits</h2><div className="events">{state?.ledger.length ? state.ledger.slice(0, 30).map(row => <div className="ledger-row" key={row.id}><div><span>{creditLabel(row.kind)}</span><small>{displayTime(row.created_at)}</small></div><strong className={row.amount > 0 ? 'positive' : ''}>{row.amount > 0 ? '+' : ''}{row.amount}</strong></div>) : <p className="empty">Payments and refunds will appear here.</p>}</div></section></div></div>
      <div hidden={section !== 'developer'} className="developer-page">
        <section className="panel stack"><ContributionToggle label="Developer options" status={developerEnabled ? 'On for this device' : 'Off'} checked={developerEnabled} onChange={changeDeveloperOptions} /><p>Advanced controls and diagnostics. Sharing stays unchanged.</p></section>
        {developerEnabled && <div className="developer-content">
          <div ref={setDeveloperTarget} />
          <section className="panel stack"><h2>Image finishing</h2><label>Device name<input value={deviceName} disabled={!!localId} onChange={e => setDeviceName(e.target.value)} maxLength={80} /></label><LimitsForm value={limits} onChange={setLimits} /><small>Changes apply the next time you turn Finish images on.</small><p className="worker-status" role="status">{workerMessage}</p></section>
          <div ref={setRequestTarget} />
          <section className="panel stack"><h2>Device details</h2><div className="device-grid">{state?.devices.map(device => <DeviceCard key={device.id} device={device} now={state.server_time} own={device.owner_id === state.user.id && device.id !== managedId && device.id !== localId} local={device.id === localId} busy={!!busy} onUpdate={patch => action(device.id, async () => { await api.request(`/devices/${device.id}`, patch, 'PATCH'); })} />)}</div></section>
          <section className="panel stack"><h2>Request details</h2>{state?.jobs.filter(job => job.owner_id === state.user.id).map(job => <JobDiagnostics key={job.id} job={job} devices={state.devices} />)}</section>
          <section className="panel stack"><h2>Manual worker pairing</h2><p>Use this token only in your own worker terminal.</p><button className="secondary" disabled={!!busy} onClick={() => { void action('pairing', async () => { await copyText(session.token); setPairingCopied(true); }); }}>{pairingCopied ? 'Pairing token copied' : 'Copy worker pairing token'}</button><small>Set POCKETGRID_SESSION_TOKEN when starting a prepared worker. Never share the token.</small><p>Grid address: <code>{session.server || location.origin}</code></p></section>
        </div>}
      </div>
    </main>
  </div></>;

}

function LimitsForm({ value, onChange, cpu = false }: { value: Limits; onChange: (limits: Limits) => void; cpu?: boolean }) {
  return <div className="limits">{cpu && <label>CPU threads<input type="number" min="1" max="8" value={value.cpu_threads} onChange={e => onChange({ ...value, cpu_threads: Number(e.target.value) })} /></label>}<label>Largest image<select value={value.max_pixels} onChange={e => onChange({ ...value, max_pixels: Number(e.target.value) })}><option value={65536}>256 × 256</option><option value={147456}>384 × 384</option><option value={262144}>512 × 512</option></select></label><label>Share for<select value={value.session_minutes} onChange={e => onChange({ ...value, session_minutes: Number(e.target.value) })}><option value={5}>5 minutes</option><option value={15}>15 minutes</option><option value={30}>30 minutes</option><option value={60}>60 minutes</option></select></label></div>;
}

function CreateJob({ api, state, onCreated, developerTarget }: { api: Api; state: Snapshot | null; onCreated: (job: Job) => void; developerTarget: HTMLElement | null }) {
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
  return <form className="stack" onSubmit={submit}><h2>Your prompt</h2><label>Describe your image<textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={3} maxLength={1000} required /></label><small>{minimum} credits estimated · {state?.balance ?? '—'} available</small><details><summary>Options</summary><div className="stack"><div className="limits"><label>Images<select value={count} onChange={e => { const next = Number(e.target.value); setCount(next); setBudget(Math.max(budget, next * ((state?.pricing.generate ?? 6) + (state?.pricing.finalize ?? 1)) + (state?.pricing.fee ?? 1))); }}>{[1, 2, 3, 4].map(value => <option key={value}>{value}</option>)}</select></label><label>Size<select value={size} onChange={e => setSize(Number(e.target.value))}>{[256, 384, 512].map(value => <option key={value} value={value}>{value} × {value}</option>)}</select></label></div><label>Maximum budget <span className="muted">(sandbox credits)</span><input type="number" min={minimum} max={state?.balance ?? 100} value={budget} onChange={e => setBudget(Number(e.target.value))} required /></label></div></details>{acceptedJob && <p className="worker-status" role="status">{jobAcknowledgement(acceptedJob)}</p>}{error && <p className="error" role="alert">{error}</p>}<button disabled={busy || !state || !prompt.trim() || budget < minimum || budget > (state?.balance ?? 0)}>{busy ? 'Submitting request…' : 'Create image'}</button><small>Reserves {budget} credits. Unused credits return.</small>{developerTarget && createPortal(<section className="panel stack"><h2>Request settings</h2><label>Model steps<input type="number" min="4" max="30" value={steps} onChange={e => setSteps(Math.max(4, Math.min(30, Number(e.target.value) || 4)))} required /></label><small>{count * (state?.pricing.generate ?? 6)} generation + {count * (state?.pricing.finalize ?? 1)} finishing + {state?.pricing.fee ?? 1} service fee.</small><label className="check"><input type="checkbox" checked={agent} onChange={e => setAgent(e.target.checked)} disabled={!state?.agent.available && !agent} />Let the planner choose devices{!state?.agent.available && <span className="muted"> (not configured)</span>}</label><small>{agent ? 'AWS Strands plans with the configured chat model. A laptop still generates your image.' : 'Direct queue · available compatible devices accept the work.'}</small></section>, developerTarget)}</form>;
}

function DeviceCard({ device, now, own, local, busy, onUpdate }: { device: Device; now: number; own: boolean; local: boolean; busy: boolean; onUpdate: (patch: { enabled?: boolean; limits?: Limits }) => Promise<void> }) {
  const [limits, setLimits] = useState(device.limits);
  const progress = Math.max(0, Math.min(1, device.telemetry.progress ?? 0));
  const sharing = isSharing(device, now);
  const pausable = canPauseDevice(device, now);
  return <article className="device"><div className="section-title"><h3>{device.name}{local ? ' · this window' : ''}</h3><span className={`dot ${device.online ? 'online' : ''}`} aria-label={device.online ? 'Online' : 'Offline'} /></div><p className="muted">{device.kind} · {device.capabilities.includes('image_generate') ? device.capabilities.includes('image_finalize') ? 'Image generation + export' : 'Image generation' : 'Image export'}</p><div className="device-line"><span>{deviceStatus(device, now)}</span><strong>{device.earned} earned</strong></div>{sharing && device.active_task_id && <><progress value={progress} max="1" aria-label="Current image progress" /><small>{device.telemetry.stage || 'Processing'} · {Math.round(progress * 100)}%</small></>}<details><summary>Measured usage</summary><p className="telemetry" aria-label="Measured resource use">{device.telemetry.backend || 'No compute running'}{device.telemetry.rss_mb != null ? ` · ${Math.round(device.telemetry.rss_mb)} MB process memory` : ''}{device.telemetry.cpu_percent != null ? ` · ${device.telemetry.cpu_percent.toFixed(0)}% process CPU` : ''}</p></details>{device.session_expires_at && sharing ? <small>Session ends {displayTime(device.session_expires_at)}</small> : null}{own && <><div className="button-row"><button className="secondary" disabled={busy || (!pausable && !canStartDevice(device, local))} onClick={() => void onUpdate({ enabled: !pausable })}>{pausable ? 'Pause' : 'Start sharing'}</button></div>{!local && <details><summary>Workload limits</summary><LimitsForm value={limits} onChange={setLimits} cpu={device.kind === 'python'} /><button className="secondary" disabled={busy || !Number.isInteger(limits.cpu_threads) || limits.cpu_threads < 1 || limits.cpu_threads > 8} onClick={() => void onUpdate({ limits })}>Save limits</button>{device.kind === 'python' && <small>CPU thread limit does not cap GPU usage. One task runs at a time.</small>}</details>}</>}</article>;
}

function JobCard({ api, job, devices, now, canStartExport, onStartExport, own, busy, onCancel }: { api: Api; job: Job; devices: Device[]; now: number; canStartExport: boolean; onStartExport: () => Promise<void>; own: boolean; busy: boolean; onCancel: () => Promise<void> }) {
  const images = visibleImages(job.images);
  const progress = jobProgress(job, devices, now);
  const queued = ['queued', 'running'].includes(job.status) && !job.tasks.some(task => task.status === 'running');
  if (queued) { progress.title = progress.waitingForExport ? 'Waiting to finish' : 'Waiting to create'; progress.detail = 'Waiting for a compatible device.'; }
  return <article className="job">
    <div className="section-title"><h3>{job.prompt}</h3><span className={`badge ${job.status === 'completed' ? 'good' : ''}`}>{job.status}</span></div>
    <div className="job-progress">
      <strong>{progress.title}</strong>{job.status !== 'completed' && <p>{progress.detail}</p>}
      {job.status !== 'planning' && job.status !== 'completed' && <><progress value={progress.completed} max={progress.total} aria-label="Completed generation and export steps" /><small>{progress.generated}/{job.count} generated · {progress.finalized}/{job.count} exports verified</small></>}
      {progress.waitingForExport && canStartExport && <><button className="secondary" disabled={busy} onClick={() => void onStartExport()}>Turn on Finish images</button><small>Keep this window open. Turn off in Contribute to pause.</small></>}
    </div>

    {images.length > 0 && <div className="gallery">{images.map(image => <ImageCard key={image.task_id} api={api} path={image.url} title={`Image ${image.variant + 1}`} verified={image.verified} />)}</div>}


    {job.receipt ? <details className="receipt-details"><summary>Receipt · {job.receipt.total_charged} credits</summary><div className="receipt"><span>Reserved {job.receipt.budget}</span><span>Contributors {job.receipt.contributor_total}</span><span>Service fee {job.receipt.platform_fee}</span><span>Refund {job.receipt.refund}</span><strong>Charged {job.receipt.total_charged}</strong></div></details> : <p className="muted">Budget {job.budget} · still reserved {job.reserved} · accepted work paid {job.spent} · returned {job.refunded}</p>}
    {own && canCancelJob(job) && <button className="secondary" disabled={busy} onClick={() => void onCancel()}>Cancel request</button>}
  </article>;
}

function JobDiagnostics({ job, devices }: { job: Job; devices: Device[] }) {
  return <article className="job"><h3>{job.prompt}</h3>    <details><summary>Plan details</summary><p>{job.plan.mode === 'manual' ? 'Direct queue' : 'Planner routing'}</p></details>
    <details><summary>Devices & steps</summary><div className="task-list">{job.tasks.map(task => <div key={task.id} className="task"><div><span>{task.kind === 'image_generate' ? 'Generate' : 'Export'} image {task.variant + 1}</span><small>{task.device_id ? devices.find(device => device.id === task.device_id)?.name || 'Assigned device' : task.status === 'queued' ? 'Awaiting assignment' : 'No active assignment'}{task.attempts > 1 ? ` · attempt ${task.attempts}` : ''}</small></div><span className="muted">{task.status === 'running' ? `${Math.round((task.progress || 0) * 100)}%` : task.status}</span></div>)}</div></details></article>;
}

function NavIcon({ name }: { name: 'create' | 'contribute' | 'activity' | 'developer' }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{name === 'create' ? <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" /></> : name === 'contribute' ? <><rect x="3" y="4" width="13" height="10" rx="2" /><path d="M1 18h13" /><rect x="17" y="10" width="5" height="10" rx="1" /></> : name === 'activity' ? <><path d="M3 12h4l3-7 4 14 3-7h4" /></> : <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" /><circle cx="15" cy="17" r="3" /></>}</svg>;
}

function ImageCard({ api, path, title, verified }: { api: Api; path: string; title: string; verified?: boolean }) {
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
  return <figure className={verified === false ? 'image-verifying' : undefined} aria-busy={verified === false}>{url ? <a href={url} onClick={event => { if (!saveReady) { event.preventDefault(); return; } if (isMacDesktop) setSaveMessage('Saving…'); }} aria-label={`Save ${title}`} download={`gipu-${title.replaceAll(' ', '-').toLowerCase()}.png`}><img src={url} alt={`${title}, locally generated`} width="256" height="256" /></a> : <div className="image-placeholder">{error || 'Loading image…'}</div>}<figcaption>{title} · {imageLabel({ verified })}{url && ' · Save image'}</figcaption>{saveMessage && <small role="status">{saveMessage}</small>}</figure>;
}
