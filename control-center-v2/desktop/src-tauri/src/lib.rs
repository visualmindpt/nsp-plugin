use std::process::{Command, Child, Stdio};
use std::sync::Mutex;
use tauri::State;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
struct ServerStatus {
    running: bool,
    pid: Option<u32>,
    port: u16,
}

#[derive(Debug, Serialize, Deserialize)]
struct SystemMetrics {
    cpu_percent: f32,
    memory_percent: f32,
    memory_used_mb: f64,
    memory_total_mb: f64,
}

// Global state para o processo do servidor
struct ServerState {
    process: Mutex<Option<Child>>,
}

#[tauri::command]
fn start_inference_server(state: State<ServerState>) -> Result<String, String> {
    let mut process_guard = state.process.lock().unwrap();

    if process_guard.is_some() {
        return Err("Servidor já está a correr".to_string());
    }

    // Caminho para o projeto
    let project_dir = std::env::current_dir()
        .map_err(|e| format!("Erro ao obter diretório: {}", e))?
        .parent()
        .ok_or("Erro ao obter diretório pai")?
        .parent()
        .ok_or("Erro ao obter diretório raiz")?
        .to_path_buf();

    // Comando para iniciar o servidor
    #[cfg(target_os = "macos")]
    let child = Command::new("sh")
        .arg("-c")
        .arg(format!(
            "cd '{}' && source venv/bin/activate && python -m uvicorn services.server:app --host 0.0.0.0 --port 5001",
            project_dir.display()
        ))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Erro ao iniciar servidor: {}", e))?;

    #[cfg(target_os = "windows")]
    let child = Command::new("cmd")
        .args(["/C", &format!(
            "cd /d \"{}\" && venv\\Scripts\\activate && python -m uvicorn services.server:app --host 0.0.0.0 --port 5001",
            project_dir.display()
        )])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Erro ao iniciar servidor: {}", e))?;

    let pid = child.id();
    *process_guard = Some(child);

    Ok(format!("Servidor iniciado com PID: {}", pid))
}

#[tauri::command]
fn stop_inference_server(state: State<ServerState>) -> Result<String, String> {
    let mut process_guard = state.process.lock().unwrap();

    if let Some(mut process) = process_guard.take() {
        process.kill()
            .map_err(|e| format!("Erro ao parar servidor: {}", e))?;
        Ok("Servidor parado com sucesso".to_string())
    } else {
        Err("Nenhum servidor a correr".to_string())
    }
}

#[tauri::command]
fn server_status(state: State<ServerState>) -> ServerStatus {
    let process_guard = state.process.lock().unwrap();

    match &*process_guard {
        Some(process) => ServerStatus {
            running: true,
            pid: Some(process.id()),
            port: 5001,
        },
        None => {
            // Verificar se existe um processo a correr na porta 5001
            let port_in_use = check_port_in_use(5001);

            ServerStatus {
                running: port_in_use,
                pid: None,
                port: 5001,
            }
        }
    }
}

#[tauri::command]
fn panic_button() -> Result<String, String> {
    // PANIC BUTTON: Mata TODOS os processos Python
    let killed_count;

    #[cfg(target_os = "macos")]
    {
        let output = Command::new("pkill")
            .arg("-9")
            .arg("python")
            .output()
            .map_err(|e| format!("Erro ao executar pkill: {}", e))?;

        killed_count = if output.status.success() {
            "todos os processos Python"
        } else {
            "0"
        };
    }

    #[cfg(target_os = "windows")]
    {
        let output = Command::new("taskkill")
            .args(["/F", "/IM", "python.exe"])
            .output()
            .map_err(|e| format!("Erro ao executar taskkill: {}", e))?;

        killed_count = if output.status.success() {
            "todos os processos Python"
        } else {
            "0"
        };
    }

    Ok(format!("🚨 PANIC BUTTON ATIVADO! Terminados {} processos", killed_count))
}

#[tauri::command]
fn get_system_metrics() -> Result<SystemMetrics, String> {
    // Obter métricas do sistema usando comandos nativos

    #[cfg(target_os = "macos")]
    {
        // CPU usage
        let cpu_output = Command::new("sh")
            .arg("-c")
            .arg("ps -A -o %cpu | awk '{s+=$1} END {print s}'")
            .output()
            .map_err(|e| format!("Erro ao obter CPU: {}", e))?;

        let cpu_str = String::from_utf8_lossy(&cpu_output.stdout);
        let cpu_percent: f32 = cpu_str.trim().parse().unwrap_or(0.0);

        // Memory usage
        let mem_output = Command::new("sh")
            .arg("-c")
            .arg("vm_stat | awk '/Pages active/ {print $3}' | sed 's/\\.//'")
            .output()
            .map_err(|e| format!("Erro ao obter memória: {}", e))?;

        let mem_str = String::from_utf8_lossy(&mem_output.stdout);
        let pages_active: f64 = mem_str.trim().parse().unwrap_or(0.0);
        let memory_used_mb = (pages_active * 4096.0) / (1024.0 * 1024.0);

        // Total memory
        let total_output = Command::new("sysctl")
            .arg("-n")
            .arg("hw.memsize")
            .output()
            .map_err(|e| format!("Erro ao obter memória total: {}", e))?;

        let total_str = String::from_utf8_lossy(&total_output.stdout);
        let total_bytes: f64 = total_str.trim().parse().unwrap_or(0.0);
        let memory_total_mb = total_bytes / (1024.0 * 1024.0);

        let memory_percent = if memory_total_mb > 0.0 {
            (memory_used_mb / memory_total_mb) * 100.0
        } else {
            0.0
        };

        Ok(SystemMetrics {
            cpu_percent,
            memory_percent: memory_percent as f32,
            memory_used_mb,
            memory_total_mb,
        })
    }

    #[cfg(target_os = "windows")]
    {
        // Windows implementation usando WMIC
        let cpu_output = Command::new("wmic")
            .args(["cpu", "get", "loadpercentage"])
            .output()
            .map_err(|e| format!("Erro ao obter CPU: {}", e))?;

        let cpu_str = String::from_utf8_lossy(&cpu_output.stdout);
        let cpu_percent: f32 = cpu_str
            .lines()
            .nth(1)
            .and_then(|s| s.trim().parse().ok())
            .unwrap_or(0.0);

        let mem_output = Command::new("wmic")
            .args(["OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize"])
            .output()
            .map_err(|e| format!("Erro ao obter memória: {}", e))?;

        let mem_str = String::from_utf8_lossy(&mem_output.stdout);
        let values: Vec<&str> = mem_str.lines().nth(1).unwrap_or("0 0").split_whitespace().collect();

        let free_kb: f64 = values.get(0).and_then(|s| s.parse().ok()).unwrap_or(0.0);
        let total_kb: f64 = values.get(1).and_then(|s| s.parse().ok()).unwrap_or(0.0);

        let memory_total_mb = total_kb / 1024.0;
        let memory_used_mb = (total_kb - free_kb) / 1024.0;
        let memory_percent = if memory_total_mb > 0.0 {
            (memory_used_mb / memory_total_mb) * 100.0
        } else {
            0.0
        };

        Ok(SystemMetrics {
            cpu_percent,
            memory_percent: memory_percent as f32,
            memory_used_mb,
            memory_total_mb,
        })
    }
}

fn check_port_in_use(port: u16) -> bool {
    #[cfg(target_os = "macos")]
    {
        let output = Command::new("lsof")
            .arg("-i")
            .arg(format!(":{}", port))
            .output();

        match output {
            Ok(out) => !out.stdout.is_empty(),
            Err(_) => false,
        }
    }

    #[cfg(target_os = "windows")]
    {
        let output = Command::new("netstat")
            .args(["-ano", "|", "findstr", &format!(":{}", port)])
            .output();

        match output {
            Ok(out) => !out.stdout.is_empty(),
            Err(_) => false,
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build()
        )
        .manage(ServerState {
            process: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            start_inference_server,
            stop_inference_server,
            server_status,
            panic_button,
            get_system_metrics,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
