// The Python worker is a desktop process; phones and tablets contribute exports from the webview.
#[cfg(desktop)]
mod worker;

#[cfg(desktop)]
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init());

    #[cfg(desktop)]
    let builder = builder
        .manage(worker::WorkerManager::default())
        .manage(worker::ModelManager::default())
        .invoke_handler(tauri::generate_handler![
            worker::worker_defaults,
            worker::connect_worker,
            worker::worker_status,
            worker::disconnect_worker,
            worker::model_status,
            worker::download_model,
            worker::cancel_model_download,
        ])
        .on_window_event(|window, event| {
            if matches!(
                event,
                tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed
            ) {
                window.state::<worker::WorkerManager>().disconnect();
            }
        });

    builder
        .build(tauri::generate_context!())
        .expect("PocketGrid could not start")
        .run(|_app, _event| {
            #[cfg(desktop)]
            if matches!(
                _event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                _app.state::<worker::WorkerManager>().disconnect();
                _app.state::<worker::ModelManager>().cancel();
            }
        });
}
