"""
schedule_setup.py — Configuração de agendamento automático

Instala (ou remove) a tarefa agendada para executar a automação diariamente.

Suporta:
  - Windows  → Windows Task Scheduler (schtasks)
  - macOS    → launchd (plist em ~/Library/LaunchAgents)
  - Linux    → crontab

Uso:
    python schedule_setup.py install    # Instalar agendamento
    python schedule_setup.py remove     # Remover agendamento
    python schedule_setup.py status     # Ver estado atual
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
TASK_NAME   = "AutomatismoContasPagar"
PLIST_LABEL = f"com.local.{TASK_NAME.lower()}"
DEFAULT_HOUR   = 8    # Hora de execução
DEFAULT_MINUTE = 0


def get_project_dir() -> Path:
    # Este ficheiro está em config/ — subir um nível para o raiz do projeto
    return Path(__file__).parent.parent.resolve()


def get_python_exec() -> str:
    """Caminho absoluto do Python no venv."""
    project = get_project_dir()
    if platform.system() == "Windows":
        python = project / "venv" / "Scripts" / "python.exe"
    else:
        python = project / "venv" / "bin" / "python"
    if python.exists():
        return str(python)
    return sys.executable


# ---------------------------------------------------------------------------
# Windows — Task Scheduler
# ---------------------------------------------------------------------------

def install_windows(hour: int, minute: int):
    project   = get_project_dir()
    script    = project / "config" / "run_automation.bat"
    time_str  = f"{hour:02d}:{minute:02d}"

    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{script}"',
        "/SC", "DAILY",
        "/ST", time_str,
        "/RL", "HIGHEST",
        "/F",  # Sobrescrever se já existir
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Tarefa '{TASK_NAME}' criada no Task Scheduler — todos os dias às {time_str}")
    else:
        print(f"❌ Erro: {result.stderr.strip()}")
        sys.exit(1)


def remove_windows():
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Tarefa '{TASK_NAME}' removida do Task Scheduler")
    else:
        print(f"⚠️  {result.stderr.strip()}")


def status_windows():
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Tarefa '{TASK_NAME}' não encontrada no Task Scheduler.")


# ---------------------------------------------------------------------------
# macOS — launchd
# ---------------------------------------------------------------------------

def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def install_macos(hour: int, minute: int):
    project = get_project_dir()
    python  = get_python_exec()
    plist   = _plist_path()

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>src.main</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{project}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>{project}/logs/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{project}/logs/launchd_stderr.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(plist_content, encoding="utf-8")

    # Carregar no launchd
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ launchd job '{PLIST_LABEL}' instalado — todos os dias às {hour:02d}:{minute:02d}")
        print(f"   Plist: {plist}")
    else:
        print(f"❌ Erro ao carregar plist: {result.stderr.strip()}")
        sys.exit(1)


def remove_macos():
    plist = _plist_path()
    if plist.exists():
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        plist.unlink()
        print(f"✅ launchd job '{PLIST_LABEL}' removido")
    else:
        print(f"⚠️  Plist não encontrado: {plist}")


def status_macos():
    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL],
        capture_output=True, text=True,
    )
    plist = _plist_path()
    if result.returncode == 0:
        print(f"✅ Job ativo: {PLIST_LABEL}")
        print(result.stdout)
    else:
        print(f"Job '{PLIST_LABEL}' não está ativo.")
    print(f"   Plist: {plist} ({'existe' if plist.exists() else 'não encontrado'})")


# ---------------------------------------------------------------------------
# Linux — crontab
# ---------------------------------------------------------------------------

CRON_MARKER = f"# {TASK_NAME}"


def install_linux(hour: int, minute: int):
    project = get_project_dir()
    script  = project / "config" / "run_automation.sh"

    cron_line = f"{minute} {hour} * * * {script}  {CRON_MARKER}"

    # Ler crontab actual
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    # Remover entradas anteriores desta tarefa
    lines = [l for l in existing.splitlines() if CRON_MARKER not in l]
    lines.append(cron_line)

    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)

    if proc.returncode == 0:
        print(f"✅ Tarefa cron instalada — todos os dias às {hour:02d}:{minute:02d}")
        print(f"   {cron_line}")
    else:
        print("❌ Erro ao instalar cron")
        sys.exit(1)


def remove_linux():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        print("⚠️  Sem crontab para este utilizador.")
        return
    lines = [l for l in result.stdout.splitlines() if CRON_MARKER not in l]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    print(f"✅ Entrada cron '{TASK_NAME}' removida")


def status_linux():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode == 0:
        matches = [l for l in result.stdout.splitlines() if CRON_MARKER in l]
        if matches:
            print(f"✅ Tarefa encontrada no crontab:")
            for m in matches:
                print(f"   {m}")
        else:
            print(f"Tarefa '{TASK_NAME}' não encontrada no crontab.")
    else:
        print("Sem crontab configurado.")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def prompt_time() -> tuple[int, int]:
    print(f"\nHora de execução diária (padrão: {DEFAULT_HOUR:02d}:{DEFAULT_MINUTE:02d})")
    try:
        raw = input("  Introduza hora:minuto (ex: 08:00) ou Enter para padrão: ").strip()
        if raw:
            h, m = raw.split(":")
            return int(h), int(m)
    except (ValueError, KeyboardInterrupt):
        pass
    return DEFAULT_HOUR, DEFAULT_MINUTE


def main():
    os_name = platform.system()
    args    = sys.argv[1:]
    action  = args[0].lower() if args else "help"

    if action == "install":
        hour, minute = prompt_time()
        print(f"\n⚙️  A instalar para {os_name}...")
        if os_name == "Windows":
            install_windows(hour, minute)
        elif os_name == "Darwin":
            install_macos(hour, minute)
        else:
            install_linux(hour, minute)

    elif action == "remove":
        if os_name == "Windows":
            remove_windows()
        elif os_name == "Darwin":
            remove_macos()
        else:
            remove_linux()

    elif action == "status":
        if os_name == "Windows":
            status_windows()
        elif os_name == "Darwin":
            status_macos()
        else:
            status_linux()

    else:
        print(__doc__)
        print(f"Sistema detectado: {os_name}")
        print(f"Diretório do projeto: {get_project_dir()}")
        print(f"Python venv: {get_python_exec()}")


if __name__ == "__main__":
    main()
