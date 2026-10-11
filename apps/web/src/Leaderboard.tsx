import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, ApiError, errorMessage } from './api';

type Metric = 'overall' | 'work' | 'availability' | 'credits';
type Metrics = { rank: number | null; score: number; availability_seconds: number; credits_used: number; completed_tasks: number; images_created: number };
type Entry = Omit<Metrics, 'rank'> & { rank: number; nickname: string; is_you: boolean };
type Board = { week_start: number; week_end: number; server_time: number; enabled: boolean; nickname: string | null; self: Metrics; entries: Entry[]; member_count: number; metric: Metric };
const metrics: { id: Metric; label: string }[] = [
  { id: 'overall', label: 'Overall' }, { id: 'work', label: 'Work' },
  { id: 'availability', label: 'Available' }, { id: 'credits', label: 'Used' },
];
function duration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return seconds > 0 && seconds < 60 ? '<1m' : minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
function pointsLabel(points: number) { return points >= 150 ? 'Grid anchor' : points >= 75 ? 'Builder' : points >= 20 ? 'Spark' : 'Getting started'; }
function number(value: number) { return value.toLocaleString(); }
function metricValue(entry: Metrics | Entry, metric: Metric) {
  return metric === 'availability' ? duration(entry.availability_seconds) : number(metric === 'work' ? entry.completed_tasks : metric === 'credits' ? entry.credits_used : entry.score);
}
function weekLabel(board: Board) {
  const format = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
  return `${format.format(new Date(board.week_start * 1000))} – ${format.format(new Date((board.week_end - 1) * 1000))}`;
}
function Glyph({ kind }: { kind: 'work' | 'image' | 'clock' | 'check' }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{kind === 'check' ? <path d="m5 12 4 4L19 6" /> : kind === 'clock' ? <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></> : kind === 'image' ? <><rect x="4" y="4" width="16" height="16" rx="4" /><circle cx="9" cy="9" r="1" /><path d="m5 17 5-5 4 4 3-3 3 4" /></> : <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" /></>}</svg>;
}

export function Leaderboard({ api, active, onCreate, onContribute, onUnauthorized }: { api: Api; active: boolean; onCreate: () => void; onContribute: () => void; onUnauthorized: () => void }) {
  const [metric, setMetric] = useState<Metric>('overall');
  const [board, setBoard] = useState<Board | null>(null);
  const [nickname, setNickname] = useState('');
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [unavailable, setUnavailable] = useState(false);
  const [reload, setReload] = useState(0);
  const version = useRef(0);
  const mounted = useRef(false);
  const saving = useRef(false);
  const currentRequest = useRef<AbortController | null>(null);
  const authFailure = useRef(onUnauthorized);
  authFailure.current = onUnauthorized;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; version.current += 1; currentRequest.current?.abort(); }; }, []);
  useEffect(() => {
    if (!active) { version.current += 1; currentRequest.current?.abort(); return; }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (saving.current) { timer = setTimeout(poll, 5000); return; }
      const requestVersion = ++version.current;
      const controller = new AbortController(); currentRequest.current = controller;
      try {
        const next = await api.request<Board>(`/leaderboard?metric=${metric}`, undefined, undefined, controller.signal);
        if (stopped || requestVersion !== version.current) return;
        setBoard(next); setUnavailable(false); setError('');
      } catch (failure) {
        if (stopped || requestVersion !== version.current || controller.signal.aborted) return;
        if (failure instanceof ApiError && failure.status === 401) { authFailure.current(); return; }
        if (failure instanceof ApiError && failure.status === 404) { setUnavailable(true); setBoard(null); }
        else setError('Rankings couldn’t refresh. Try again.');
      } finally {
        if (!stopped) timer = setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => { stopped = true; version.current += 1; currentRequest.current?.abort(); clearTimeout(timer); };
  }, [api, active, metric, reload]);

  async function saveProfile(enabled: boolean) {
    if (saving.current) return;
    saving.current = true; setBusy(true); setError('');
    const requestVersion = ++version.current; currentRequest.current?.abort();
    try {
      const next = await api.request<Board>('/leaderboard/profile', { enabled, nickname: enabled ? nickname.trim() : board?.nickname ?? '' }, 'PATCH');
      if (!mounted.current || requestVersion !== version.current) return;
      setBoard(next); setMetric('overall'); setEditing(false); setUnavailable(false);
    } catch (failure) {
      if (!mounted.current || requestVersion !== version.current) return;
      if (failure instanceof ApiError && failure.status === 401) authFailure.current();
      else setError(errorMessage(failure));
    } finally {
      saving.current = false;
      if (mounted.current) { setBusy(false); setReload(value => value + 1); }
    }
  }
  function submit(event: FormEvent) { event.preventDefault(); void saveProfile(true); }
  if (!active) return null;
  if (unavailable) return <section className="panel stack"><h2>Leaderboard is coming to this grid</h2><p>The coordinator needs an update.</p><button className="secondary" onClick={() => setReload(value => value + 1)}>Try again</button></section>;
  if (!board) return <section className="panel stack" aria-busy={!error}><p role={error ? 'alert' : 'status'}>{error || 'Opening this week’s board…'}</p>{error && <button className="secondary" onClick={() => setReload(value => value + 1)}>Try again</button>}</section>;
  const goals = [
    { title: 'Help with 3 tasks', count: board.self.completed_tasks, target: 3, unit: 'tasks', kind: 'work' as const, action: onContribute },
    { title: 'Create an image', count: board.self.images_created, target: 1, unit: 'images', kind: 'image' as const, action: onCreate },
    { title: 'Share for 30 minutes', count: board.self.availability_seconds, target: 1800, unit: 'seconds', kind: 'clock' as const, action: onContribute },
  ];
  const goalsDone = goals.filter(goal => goal.count >= goal.target).length;
  const metricLabel = metric === 'overall' ? 'points' : metric === 'work' ? 'tasks helped' : metric === 'credits' ? 'credits used' : 'time shared';
  return <div className="leaderboard-page">
    {error && <div className="error banner" role="alert">{error} <button className="subtle" disabled={busy} onClick={() => setReload(value => value + 1)}>Retry</button></div>}
    <div className="leaderboard-overview">
      <section className="weekly-score" aria-label="Your weekly progress">
        <div className="weekly-score-top"><span>This week</span><span>{weekLabel(board)}</span></div>
        <div className="weekly-score-body"><div><span className="weekly-score-label">Your points</span><strong>{number(board.self.score)}</strong><span className="weekly-level">{pointsLabel(board.self.score)}</span></div><div className="score-goals" role="img" aria-label={`${goalsDone} of 3 weekly goals complete`}><svg viewBox="0 0 120 120" aria-hidden="true"><circle className="score-goals-track" cx="60" cy="60" r="49" /><circle className="score-goals-progress" cx="60" cy="60" r="49" pathLength="3" strokeDasharray={`${goalsDone} 3`} /></svg><div><b>{goalsDone}<small>/3</small></b><span>Goals done</span></div></div></div>
        <div className="weekly-score-bottom"><span>{board.enabled && board.self.rank !== null ? `#${board.self.rank} this week` : 'Your progress, at your pace'}</span><span>Resets Monday</span></div>
      </section>
      <section className="panel weekly-goals"><h2>Your weekly goals</h2><div className="weekly-goal-list">{goals.map(goal => {
        const complete = goal.count >= goal.target;
        const progress = Math.min(goal.count, goal.target);
        return <button key={goal.kind} className={`weekly-goal ${complete ? 'complete' : ''}`} onClick={goal.action} aria-label={`${goal.title}. ${complete ? 'Complete' : `${goal.unit === 'seconds' ? duration(goal.count) : goal.count} of ${goal.unit === 'seconds' ? '30m' : goal.target}`}`}><span className="goal-glyph"><Glyph kind={complete ? 'check' : goal.kind} /></span><span className="goal-copy"><strong>{goal.title}</strong><span className="goal-track" role="progressbar" aria-label={goal.title} aria-valuemin={0} aria-valuemax={goal.target} aria-valuenow={progress}><i style={{ width: `${progress / goal.target * 100}%` }} /></span></span><span className="goal-count">{complete ? 'Done' : goal.unit === 'seconds' ? `${duration(goal.count)} / 30m` : `${progress} / ${goal.target}`}</span></button>;
      })}</div></section>
    </div>
    <section className="panel weekly-board" aria-label="Weekly leaderboard">
      <div className="board-heading"><div><h2>The weekly board</h2><p>{board.member_count} {board.member_count === 1 ? 'member' : 'members'} · {weekLabel(board)}</p></div><button className="secondary" disabled={busy} onClick={() => { setNickname(board.nickname ?? ''); setEditing(value => !value); }}>{editing ? 'Close' : board.enabled ? 'Your nickname' : 'Join the board'}</button></div>
      {editing && <form className="board-profile" onSubmit={submit}><label>Public nickname<input value={nickname} onChange={event => setNickname(event.target.value)} maxLength={24} required disabled={busy} autoComplete="off" placeholder="Pick a nickname" /></label><p>Your nickname and weekly totals are visible to the grid.</p><div className="button-row"><button disabled={busy || !nickname.trim()}>{busy ? 'Saving…' : board.enabled ? 'Save nickname' : 'Join the board'}</button>{board.enabled && <button type="button" className="secondary" disabled={busy} onClick={() => void saveProfile(false)}>Leave the board</button>}</div></form>}
      <div className="board-metrics" role="group" aria-label="Rank by">{metrics.map(item => <button key={item.id} aria-pressed={metric === item.id} disabled={busy} onClick={() => setMetric(item.id)}>{item.label}</button>)}</div>
      {board.metric !== metric ? <p role="status" className="empty">Updating rankings…</p> : <>
        <div className="board-column-labels" aria-hidden="true"><span>Rank</span><span>Member</span><span>{metricLabel}</span></div>
        {board.entries.length ? <ol className="board-entries">{board.entries.map((entry, index) => <li key={`${entry.nickname}:${index}`} className={entry.is_you ? 'is-you' : ''}><span className={`board-rank ${entry.rank === 1 ? 'first' : ''}`} aria-label={`Rank ${entry.rank}`}>{entry.rank.toString().padStart(2, '0')}</span><div className="board-member"><span className="board-avatar" aria-hidden="true">{entry.nickname.slice(0, 1).toUpperCase()}</span><strong>{entry.nickname}</strong>{entry.is_you && <span className="board-you">You</span>}</div><strong className="board-value">{metricValue(entry, metric)}<small>{metricLabel}</small></strong></li>)}</ol> : <div className="board-empty"><span className="empty-medal" aria-hidden="true"><Glyph kind="work" /></span><h3>A little help goes a long way.</h3><p>Be the first on this week’s board.</p></div>}
        {board.enabled && board.self.rank !== null && !board.entries.some(entry => entry.is_you) && <div className="board-personal-rank"><strong>#{board.self.rank} · You</strong><span>{metricValue(board.self, metric)} {metricLabel}</span></div>}
      </>}
      <div className="weekly-totals"><div><strong>{number(board.self.completed_tasks)}</strong><span>tasks helped</span></div><div><strong>{duration(board.self.availability_seconds)}</strong><span>available</span></div><div><strong>{number(board.self.credits_used)}</strong><span>credits used</span></div></div>
      <details className="board-rules"><summary>How points work</summary><p>10 points per accepted task for another member. 1 per credit used. 1 per 15 minutes shared, up to 32 each week.</p><p>Credits exclude refunds and payments returned to your own devices. Availability counts while sharing and connected; overlapping devices count once. Weeks reset Monday at 00:00 UTC. Points have no cash value.</p></details>
    </section>
  </div>;
}
