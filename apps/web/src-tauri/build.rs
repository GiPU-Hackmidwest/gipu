fn main() {
    // The Android secure-storage plugin is implemented in Kotlin inside the app
    // (gen/android/.../SecureStoragePlugin.kt); this declares its ACL commands.
    tauri_build::try_build(tauri_build::Attributes::new().plugin(
        "secure-storage",
        tauri_build::InlinedPlugin::new()
            .commands(&["get_secret", "set_secret", "delete_secret"])
            .default_permission(tauri_build::DefaultPermissionRule::AllowAllCommands),
    ))
    .expect("failed to run tauri-build");
}
