# utils/logger.py
import logging
import sys
from datetime import datetime
import json
from pathlib import Path

class MCPGovernanceLogger:
    """Centralized logging for MCP Governance Bridge."""
    
    def __init__(self, name: str = "mcp-governance", level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup logging handlers."""
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            file_handler = logging.FileHandler(log_dir / 'mcp_governance.log')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            
            print(f"📝 Logging to {log_dir / 'mcp_governance.log'}")
            
        except Exception as e:
            self.logger.warning(f"Could not create file handler: {e}")
    
    def get_logger(self):
        """Get the logger instance."""
        return self.logger

# Global logger instance
logger = MCPGovernanceLogger().get_logger()