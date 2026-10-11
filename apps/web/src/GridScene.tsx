import type { Device, Snapshot } from './types';
import { isSharing } from './deviceStatus';

/** A view of observed grid capacity, never an animated simulation of work. */
export function GridScene({ state, onOpen }: { state: Snapshot | null; onOpen: () => void }) {
  const live = state?.devices.filter(d => d.online) ?? [];
  const laptops = live.filter(d => d.capabilities.includes('image_generate'));
  const finishers = live.filter(d => d.capabilities.includes('image_finalize'));
  const count = (items: Device[]) => items.filter(d => isSharing(d, state?.server_time ?? NaN)).length;
  return <aside className="grid-scene" aria-label="Live grid devices">
    <div className="scene-top"><span>Your grid</span><button className="round-control" onClick={onOpen} aria-label="View grid devices"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12" /></svg></button></div>
    <div className="device-landscape">
      <svg className="grid-path" viewBox="0 0 400 330" aria-hidden="true"><path d="M108 88C330 88 45 238 293 238" /></svg>
      <div className="hardware laptop"><div className="laptop-screen"><span className="screen-grid">{Array.from({ length: 9 }, (_, i) => <i key={i} />)}</span></div><div className="laptop-base" /></div>
      <div className="device-count laptop-count"><strong>{state ? count(laptops) : '—'}</strong><span>{count(laptops) === 1 ? 'laptop' : 'laptops'}</span></div>
      <div className="hardware phone"><div className="phone-screen"><span /></div></div>
      <div className="device-count phone-count"><strong>{state ? count(finishers) : '—'}</strong><span>{count(finishers) === 1 ? 'finisher' : 'finishers'}</span></div>
    </div>
    <div className="scene-bottom"><span className="status-pin" /><span>{state ? `${live.length} connected` : 'Checking grid…'}</span><small>Sharing now</small></div>
  </aside>;
}
