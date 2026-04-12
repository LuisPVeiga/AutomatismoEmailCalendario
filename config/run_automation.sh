#!/usr/bin/env bash
# =====================================================
#  Automação de Contas a Pagar — macOS / Linux
#  Usar com cron ou launchd (macOS)
#
#  Exemplos cron (crontab -e):
#    Todos os dias às 08:00:
#      0 8 * * * /caminho/para/run_automation.sh
#    Também às 13:00:
#      0 8,13 * * * /caminho/para/run_automation.sh
# =====================================================
set -euo pipefail

# -- Ir para o diretório do projeto (um nível acima de config/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." 

# -- Criar pasta de logs se não existir
mkdir -p logs

# -- Timestamp para log rotacionado
TIMESTAMP=$(date +"%Y%m%d_%H%M")
LOG_FILE="logs/run_${TIMESTAMP}.log"

echo "[${TIMESTAMP}] A iniciar automação..." | tee -a logs/logs.txt

# -- Verificar ambiente virtual
if [[ ! -f venv/bin/activate ]]; then
    echo "[ERRO] Ambiente virtual não encontrado em venv/"
    echo "       Execute: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# -- Ativar venv e executar
source venv/bin/activate
python -m src.main 2>&1 | tee "$LOG_FILE" >> logs/logs.txt
EXIT_CODE=${PIPESTATUS[0]}

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "[${TIMESTAMP}] Execução concluída com sucesso." | tee -a logs/logs.txt
else
    echo "[${TIMESTAMP}] ERRO na execução. Código: ${EXIT_CODE}" | tee -a logs/logs.txt
fi

# -- Limpar logs com mais de 30 dias
find logs -name "run_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
