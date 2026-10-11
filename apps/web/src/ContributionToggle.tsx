import { useId } from 'react';

export type ContributionToggleProps = {
  label: string;
  status: string;
  checked: boolean;
  busy?: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
};

/** Busy announces an operation; callers may leave the switch enabled to cancel it. */
export function ContributionToggle({ label, status, checked, busy = false, disabled = false, onChange }: ContributionToggleProps) {
  const id = useId();
  return <div className="contribution-toggle">
    <div className="contribution-toggle-copy"><h2 id={`${id}-label`}>{label}</h2><p id={`${id}-status`} role="status">{status}</p></div>
    <button type="button" role="switch" className="contribution-switch" aria-labelledby={`${id}-label`} aria-describedby={`${id}-status`} aria-checked={checked} aria-busy={busy || undefined} disabled={disabled} onClick={() => onChange(!checked)}><span className="contribution-switch-thumb" aria-hidden="true" /></button>
  </div>;
}
