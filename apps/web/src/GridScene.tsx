import type { Snapshot } from './types';
import { gridCounts } from './publicPresentation';

/** A view of observed grid capacity, never an animated simulation of work. */
export function GridScene({ state, onOpen }: { state: Snapshot | null; onOpen: () => void }) {
  const counts = gridCounts(state);
  return <aside className="grid-scene" aria-label="Grid capacity">
    <div className="scene-top"><span>Your grid</span><button className="round-control" onClick={onOpen} aria-label="Open contribution controls"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 18 18 6M6 6h12v12" /></svg></button></div>
    <div className="device-landscape">
      <svg className="grid-path" viewBox="0 0 400 330" aria-hidden="true"><path d="M108 88C330 88 45 238 293 238" /><circle className="route-waypoint" cx="108" cy="88" r="5" /><circle className="route-waypoint" cx="293" cy="238" r="5" /></svg>
      <div className="hardware laptop"><div className="laptop-screen"><span className="screen-grid">{Array.from({ length: 9 }, (_, i) => <i key={i} />)}</span></div><div className="laptop-base" /></div>
      <div className="device-count laptop-count"><strong>{counts?.ready_to_create ?? '—'}</strong><span>Ready to create</span></div>
      <div className="hardware phone"><div className="phone-screen"><span /></div></div>
      <div className="device-count phone-count"><strong>{counts?.ready_to_finish ?? '—'}</strong><span>Ready to finish</span></div>
    </div>
    <div className="scene-bottom"><span className="status-pin" /><span>{counts ? `${counts.connected} connected` : state ? 'Counts unavailable' : 'Checking grid…'}</span><small>{counts ? 'Across your grid' : 'Update coordinator'}</small></div>
  </aside>;
}
