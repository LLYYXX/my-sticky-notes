use std::{
    io::{Read, Write},
    net::{IpAddr, Ipv4Addr, SocketAddr, TcpListener, TcpStream},
    sync::Arc,
    thread,
    time::Duration,
};

use tauri::{AppHandle, Manager};

const SERVICE_PORT: u16 = 45_419;
const ACTIVATE: &[u8] = b"my-sticky-notes:activate:v1";
const ACKNOWLEDGE: &[u8] = b"my-sticky-notes:ack:v1";
const CONNECT_TIMEOUT: Duration = Duration::from_millis(300);
const READ_TIMEOUT: Duration = Duration::from_millis(400);
const NOTIFY_ATTEMPTS: usize = 8;

pub enum AcquireResult {
    Primary(InstanceGuard),
    Existing,
}

pub struct InstanceGuard {
    listener: Arc<TcpListener>,
}

pub fn acquire() -> Result<AcquireResult, String> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), SERVICE_PORT);
    match TcpListener::bind(address) {
        Ok(listener) => Ok(AcquireResult::Primary(InstanceGuard {
            listener: Arc::new(listener),
        })),
        Err(error) if error.kind() == std::io::ErrorKind::AddrInUse => {
            notify_primary(address)?;
            Ok(AcquireResult::Existing)
        }
        Err(error) => Err(format!("unable to reserve single-instance endpoint: {error}")),
    }
}

pub fn begin_listening(guard: InstanceGuard, app: AppHandle) {
    let listener = guard.listener.clone();
    app.manage(guard);
    thread::Builder::new()
        .name("my-sticky-notes-single-instance".to_owned())
        .spawn(move || {
            for stream in listener.incoming().flatten() {
                if is_activation(stream) {
                    focus_main_window(&app);
                }
            }
        })
        .expect("single-instance listener thread should start");
}

pub fn focus_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn notify_primary(address: SocketAddr) -> Result<(), String> {
    let mut last_error = None;
    for _ in 0..NOTIFY_ATTEMPTS {
        match TcpStream::connect_timeout(&address, CONNECT_TIMEOUT) {
            Ok(mut stream) => {
                let _ = stream.set_read_timeout(Some(READ_TIMEOUT));
                if stream.write_all(ACTIVATE).is_ok() {
                    let mut acknowledgement = [0; ACKNOWLEDGE.len()];
                    if stream.read_exact(&mut acknowledgement).is_ok() && acknowledgement == ACKNOWLEDGE {
                        return Ok(());
                    }
                }
            }
            Err(error) => last_error = Some(error),
        }
        thread::sleep(Duration::from_millis(75));
    }
    Err(format!(
        "single-instance endpoint is occupied but did not acknowledge activation: {}",
        last_error
            .map(|error| error.to_string())
            .unwrap_or_else(|| "invalid response".to_owned())
    ))
}

fn is_activation(mut stream: TcpStream) -> bool {
    let _ = stream.set_read_timeout(Some(READ_TIMEOUT));
    let mut message = [0; ACTIVATE.len()];
    if stream.read_exact(&mut message).is_err() || message != ACTIVATE {
        return false;
    }
    stream.write_all(ACKNOWLEDGE).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn activation_protocol_has_fixed_message_sizes() {
        assert!(ACTIVATE.starts_with(b"my-sticky-notes:"));
        assert!(ACKNOWLEDGE.starts_with(b"my-sticky-notes:"));
    }
}
