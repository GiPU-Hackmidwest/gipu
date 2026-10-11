#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod worker;

use tauri::Manager;
#[cfg(target_os = "macos")]
use tauri::{webview::DownloadEvent, Emitter};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .manage(worker::WorkerManager::default())
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
        .invoke_handler(tauri::generate_handler![
            worker::worker_defaults,
            worker::connect_worker,
            worker::worker_status,
            worker::disconnect_worker,
        ])
        .on_window_event(|window, event| {
            if matches!(
                event,
                tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed
            ) {
                window.state::<worker::WorkerManager>().disconnect();
            }
        })
        .build(tauri::generate_context!())
        .expect("PocketGrid desktop could not start")
        .run(|app, event| {
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                app.state::<worker::WorkerManager>().disconnect();
            }
        });
}
