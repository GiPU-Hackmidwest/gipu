import { Api, errorMessage } from './api';
import type { Device, DeviceCredential, Task } from './types';

// A foreground browser executes only this fixed image transform, never arbitrary task code.
export class BrowserWorker {
  private running = false;
  private controller = new AbortController();
  private task: Task | null = null;
  private timer?: ReturnType<typeof setTimeout>;
  private heartbeat?: ReturnType<typeof setInterval>;
  private api: Api;
  constructor(readonly owner: Api, readonly credential: DeviceCredential, readonly report: (message: string) => void) { this.api = new Api(owner.server, credential.token); }
  start() {
    if (this.running) return;
    this.running = true;
    this.controller = new AbortController();
    this.report('Ready for an image export. Keep this window visible.');
    this.heartbeat = setInterval(() => { void this.beat(); }, 3000);
    void this.tick();
  }
  stop() { this.running = false; this.controller.abort(); clearTimeout(this.timer); clearInterval(this.heartbeat); this.task = null; }
  private async beat() {
    if (!this.running) return;
    try {
      const taskAtRequest = this.task;
      const result = await this.api.request<{ device: Device; lease_valid: boolean }>(`/devices/${this.credential.id}/heartbeat`, { telemetry: { backend: 'browser-canvas', stage: this.task ? 'Applying export frame' : 'Waiting for work' }, ...(this.task ? { task_id: this.task.id, lease_id: this.task.lease_id } : {}) }, undefined, this.controller.signal);
      if (!result.device.enabled || (taskAtRequest && this.task === taskAtRequest && !result.lease_valid)) { this.stop(); this.report('Sharing stopped. Start again when you’re ready.'); }
    } catch (error) { if (this.running) { this.stop(); this.report(`Sharing stopped: ${errorMessage(error)}. Start again to reconnect.`); } }
  }
  private async tick() {
    if (!this.running || document.hidden) return;
    try {
      await this.beat();
      if (!this.running) return;
      const { task, device } = await this.api.request<{ task: Task | null; device: Device }>(`/devices/${this.credential.id}/claim`, {}, undefined, this.controller.signal);
      if (!device.enabled) { this.stop(); return; }
      if (task) {
        this.task = task;
        this.report(`Exporting image ${task.variant + 1} · ${task.price} credits on acceptance`);
        const started = performance.now();
        if (task.kind !== 'image_finalize' || !task.source_url) throw new Error('Unsupported browser task');
        await this.api.request(`/tasks/${task.id}/progress`, { lease_id: task.lease_id, progress: 0.25, stage: 'Reading image' }, undefined, this.controller.signal);
        const blob = await this.api.image(task.source_url, this.controller.signal);
        const image = await createImageBitmap(blob);
        if (!this.running || document.hidden) { image.close(); return; }
        if (image.width !== task.width || image.height !== task.height) { image.close(); throw new Error('Source dimensions do not match the task'); }
        const canvas = document.createElement('canvas'); canvas.width = task.width; canvas.height = task.height;
        const context = canvas.getContext('2d');
        if (!context) { image.close(); throw new Error('Canvas is unavailable'); }
        context.drawImage(image, 0, 0); image.close();
        context.fillStyle = 'rgb(36,203,166)';
        context.fillRect(0, 0, task.width, 4); context.fillRect(0, task.height - 4, task.width, 4);
        context.fillRect(0, 0, 4, task.height); context.fillRect(task.width - 4, 0, 4, task.height);
        const png = canvas.toDataURL('image/png').split(',')[1];
        if (!this.running || document.hidden) return;
        const result = await this.api.request<{ earned: number }>(`/tasks/${task.id}/complete`, { lease_id: task.lease_id, png_base64: png, metrics: { backend: 'browser-canvas', elapsed_seconds: (performance.now() - started) / 1000 } }, undefined, this.controller.signal);
        this.report(`Export accepted · earned ${result.earned} sandbox credits`);
      }
    } catch (error) {
      if (this.running) {
        this.report(errorMessage(error));
        if (this.task) await this.api.request(`/tasks/${this.task.id}/fail`, { lease_id: this.task.lease_id, error: errorMessage(error) }, undefined, this.controller.signal).catch(() => {});
      }
    } finally { this.task = null; if (this.running) this.timer = setTimeout(() => { void this.tick(); }, 1000); }
  }
}
