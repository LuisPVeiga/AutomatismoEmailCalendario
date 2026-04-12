"""
Gestor de estado da aplicação
Responsável por rastrear emails já processados
"""

import json
import os
from typing import Set, Dict
from datetime import datetime

from src.config import STATE_FILE


class StateManager:
    """Gerenciador de estado para rastrear emails processados"""
    
    def __init__(self):
        """Inicializar o gestor de estado"""
        self.state_file = STATE_FILE
        self.processed_emails = self._load_state()
    
    def _load_state(self) -> Dict:
        """Carregar estado de arquivo"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Aviso: Erro ao carregar estado: {str(e)}")
                return {"emails": {}}
        
        return {"emails": {}, "last_run": None}
    
    def _save_state(self):
        """Salvar estado em arquivo"""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.processed_emails, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Aviso: Erro ao salvar estado: {str(e)}")
    
    def is_processed(self, email_id: str) -> bool:
        """
        Verificar se email já foi processado
        
        Args:
            email_id: ID do email do Gmail
            
        Returns:
            bool: True se ja foi processado
        """
        return email_id in self.processed_emails.get("emails", {})
    
    def mark_as_processed(self, email_id: str, data: Dict = None):
        """
        Marcar email como processado
        
        Args:
            email_id: ID do email
            data: Dados adicionais a guardar
        """
        if "emails" not in self.processed_emails:
            self.processed_emails["emails"] = {}
        
        self.processed_emails["emails"][email_id] = {
            "processed_at": datetime.now().isoformat(),
            "data": data or {},
        }
        
        self._save_state()
    
    def get_processed_count(self) -> int:
        """Obter número de emails processados"""
        return len(self.processed_emails.get("emails", {}))
    
    def set_last_run(self, timestamp: str = None):
        """
        Registrar última execução
        
        Args:
            timestamp: Timestamp ISO format (usar atual se None)
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        self.processed_emails["last_run"] = timestamp
        self._save_state()
    
    def get_last_run(self) -> str:
        """Obter data da última execução"""
        return self.processed_emails.get("last_run", "Nunca")
    
    def clear_state(self):
        """Limpar todo o estado (para testes)"""
        self.processed_emails = {"emails": {}, "last_run": None}
        self._save_state()
        print("⚠️  Estado limpo")
    
    def get_summary(self) -> Dict:
        """Obter resumo do estado"""
        return {
            "total_processed": self.get_processed_count(),
            "last_run": self.get_last_run(),
            "state_file": self.state_file,
        }


if __name__ == "__main__":
    # Teste do StateManager
    manager = StateManager()
    
    print("=== Estado Inicial ===")
    print(json.dumps(manager.get_summary(), indent=2))
    
    # Marcar emails como processados
    print("\n=== Processando emails ===")
    manager.mark_as_processed("email_1", {"subject": "Teste 1"})
    manager.mark_as_processed("email_2", {"subject": "Teste 2"})
    manager.set_last_run()
    
    print("=== Estado Após Processamento ===")
    print(json.dumps(manager.get_summary(), indent=2))
    
    # Verificar se emails foram marcados
    print("\n=== Verificando emails ===")
    print(f"Email 1 processado: {manager.is_processed('email_1')}")
    print(f"Email 2 processado: {manager.is_processed('email_2')}")
    print(f"Email 3 processado: {manager.is_processed('email_3')}")
