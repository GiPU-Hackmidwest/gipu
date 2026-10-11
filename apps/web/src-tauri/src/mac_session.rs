//! Session credentials stay in the macOS login Keychain, never app preferences.
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Session {
    token: String,
    name: String,
    server: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    user_id: Option<String>,
}

impl Session {
    fn validate(&self) -> Result<(), String> {
        if self.token.is_empty() || self.token.len() > 8192 || self.name.len() > 1024 {
            return Err("Invalid saved sign-in.".into());
        }
        if !self.server.is_empty() {
            let url = url::Url::parse(&self.server).map_err(|_| "Invalid grid address.")?;
            if !matches!(url.scheme(), "http" | "https") || url.host_str().is_none()
                || !url.username().is_empty() || url.password().is_some()
                || url.query().is_some() || url.fragment().is_some() || url.path() != "/" {
                return Err("Invalid grid address.".into());
            }
        }
        Ok(())
    }
}

#[cfg(target_os = "macos")]
mod keychain {
    use super::Session;
    use security_framework::passwords::{delete_generic_password, get_generic_password, set_generic_password};
    const SERVICE: &str = "dev.pocketgrid.desktop.session";
    const ACCOUNT: &str = "current-session-v1";
    const NOT_FOUND: i32 = -25300;

    pub fn load() -> Result<Option<Session>, String> {
        match get_generic_password(SERVICE, ACCOUNT) {
            Ok(bytes) => {
                let session: Session = serde_json::from_slice(&bytes).map_err(|_| "Saved sign-in could not be read.")?;
                session.validate()?;
                Ok(Some(session))
            }
            Err(error) if error.code() == NOT_FOUND => Ok(None),
            Err(_) => Err("Could not read the sign-in from Keychain. Unlock Keychain and try again.".into()),
        }
    }

    pub fn save(session: &Session) -> Result<(), String> {
        session.validate()?;
        let bytes = serde_json::to_vec(session).map_err(|_| "Could not save this sign-in.")?;
        set_generic_password(SERVICE, ACCOUNT, &bytes).map_err(|_| "Could not save the sign-in in Keychain.".into())
    }

    pub fn clear() -> Result<(), String> {
        match delete_generic_password(SERVICE, ACCOUNT) {
            Ok(()) => Ok(()),
            Err(error) if error.code() == NOT_FOUND => Ok(()),
            Err(_) => Err("Could not remove the sign-in from Keychain.".into()),
        }
    }
}

#[tauri::command]
pub fn load_mac_session() -> Result<Option<Session>, String> {
    #[cfg(target_os = "macos")]
    { keychain::load() }
    #[cfg(not(target_os = "macos"))]
    { Err("Mac Keychain is unavailable on this platform.".into()) }
}

#[tauri::command]
pub fn save_mac_session(session: Session) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    { keychain::save(&session) }
    #[cfg(not(target_os = "macos"))]
    { let _ = session; Err("Mac Keychain is unavailable on this platform.".into()) }
}

#[tauri::command]
pub fn clear_mac_session() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    { keychain::clear() }
    #[cfg(not(target_os = "macos"))]
    { Err("Mac Keychain is unavailable on this platform.".into()) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_invalid_keychain_sessions_without_touching_keychain() {
        for server in ["file:///tmp/grid", "https://user:password@example.com", "https://example.com/path", "https://example.com?token=secret"] {
            let session = Session { token: "test".into(), name: "Guest".into(), server: server.into(), user_id: None };
            assert!(session.validate().is_err());
        }
    }
}
