export type WorkerStatus = {
  phase: 'stopped' | 'starting' | 'connected' | 'failed';
  deviceId?: string | null;
  backend?: string | null;
  message: string;
};
export type ModelStatus = {
  phase: 'missing' | 'downloading' | 'ready' | 'failed';
  downloadedBytes: number;
  expectedBytes: number;
  message: string;
};
export type WorkerConnection = { projectRoot: string; server: string; sessionToken: string; backend: string; cloudGeneration?: boolean };
type Invoker = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

const nativeInvoke: Invoker = async (command, args) => {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke(command, args);
};

export class DesktopWorkerClient {
  private pending: Promise<unknown> = Promise.resolve();
  private readonly invoke: Invoker;

  constructor(invoke: Invoker = nativeInvoke) { this.invoke = invoke; }

  // Keep a late connect from overtaking a disconnect during Leave or a remount.
  private serialize<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.pending.then(operation);
    this.pending = result.catch(() => {});
    return result;
  }

  private enqueue<T>(command: string, args?: Record<string, unknown>): Promise<T> {
    return this.serialize(() => this.invoke<T>(command, args));
  }

  defaults() { return this.enqueue<{ projectRoot: string; bundled: boolean }>('worker_defaults'); }
  // The model download is independent of which account is connected, so it is not queued behind connects.
  modelStatus() { return this.invoke<ModelStatus>('model_status'); }
  downloadModel() { return this.invoke<ModelStatus>('download_model'); }
  cancelModelDownload() { return this.invoke<ModelStatus>('cancel_model_download'); }
  status() { return this.enqueue<WorkerStatus>('worker_status'); }
  connect(options: WorkerConnection) { return this.enqueue<WorkerStatus>('connect_worker', options); }
  disconnect(afterStop?: (status: WorkerStatus) => Promise<void>) {
    return this.serialize(async () => {
      const status = await this.invoke<WorkerStatus>('disconnect_worker');
      // Finish the old session's bounded Pause before a later Connect can run.
      await afterStop?.(status);
      return status;
    });
  }
}

// Survives React remounts so cleanup and a new account's connection stay ordered.
export const desktopWorker = new DesktopWorkerClient();
