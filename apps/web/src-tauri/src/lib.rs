// The Python worker is a desktop process; phones and tablets contribute exports from the webview.
#[cfg(desktop)]
mod worker;

#[cfg(desktop)]
use tauri::Manager;
#[cfg(target_os = "macos")]
use tauri::{webview::DownloadEvent, Emitter};

// Android keeps session secrets encrypted with an Android Keystore key; see SecureStoragePlugin.kt.
#[cfg(target_os = "android")]
fn secure_storage<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    tauri::plugin::Builder::new("secure-storage")
        .setup(|_app, api| {
            api.register_android_plugin("dev.pocketgrid.app", "SecureStoragePlugin")?;
            Ok(())
        })
        .build()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_clipboard_manager::init());

    // QR sign-in: gipu:// links, the camera scanner and secure session storage.
    #[cfg(target_os = "android")]
    let builder = builder
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_barcode_scanner::init())
        .plugin(secure_storage());

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
