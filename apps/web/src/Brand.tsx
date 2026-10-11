import lightWordmark from '../../../brand/gipu-wordmark.svg';
import darkWordmark from '../../../brand/gipu-wordmark-on-dark.svg';

/** Official drawn wordmark, including its unchanged live-orange dot. */
export function Brand() {
  return <div className="brand"><picture className="brand-logo"><source media="(prefers-color-scheme: dark)" srcSet={darkWordmark} /><img src={lightWordmark} width="119" height="40" alt="GiPU" /></picture></div>;
}
