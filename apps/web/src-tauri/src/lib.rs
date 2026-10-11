// The Python worker is a desktop process; phones and tablets contribute exports from the webview.
#[cfg(desktop)]
mod worker;
#[cfg(desktop)]
mod mac_session;

#[cfg(desktop)]
use tauri::Manager;
#[cfg(target_os = "macos")]
use tauri::{webview::DownloadEvent, Emitter};

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
            mac_session::load_mac_session,
            mac_session::save_mac_session,
            mac_session::clear_mac_session,
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
        .setup(|app| {
            // Preserve the configured window while adding macOS download handling.
            // WebKit cancels download links unless a handler is registered.
            for config in &app.config().app.windows {
                let builder = tauri::WebviewWindowBuilder::from_config(app, config)?;
                #[cfg(target_os = "macos")]
                let builder = builder.on_download(|webview, event| {
                    match event {
                        DownloadEvent::Requested { url, .. } => {
                            // Images are fetched with Authorization by the client first.
                            // No credentials or arbitrary remote URLs reach the downloader.
                            return url.scheme() == "blob";
                        }
                        DownloadEvent::Finished { url, success, .. } => {
                            let _ = webview.emit("image-download-finished", serde_json::json!({
                                "url": url.as_str(), "success": success
                            }));
                        }
                        _ => {}
                    }
                    true
                });
                builder.build()?;
            }
            Ok(())
        })
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
