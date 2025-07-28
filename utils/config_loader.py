# utils/config_loader.py
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib
from utils.logger import logger

class ConfigLoader:
    """Configuration loader with validation and caching."""
    
    def __init__(self, config_path: str = "mcp_governance_config.json"):
        self.config_path = Path(config_path)
        self.config_cache = {}
        self.config_hash = None
        self.default_config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration with new governance options."""
        return {
            "governance": {
                "deployment_mode": "unified",
                "base_port": 8173,
                "enable_tracking": True,
                "enable_dashboard": True,
                "mongodb_uri": "mongodb://localhost:27017",
                "auth_disabled": True,
                "transformation_strategy": "fastmcp_native"
            },
            "mcpServers": {}
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file with validation."""
        try:
            if not self.config_path.exists():
                logger.warning(f"⚠️ Config file {self.config_path} not found, using default config")
                return self.default_config
            
            with open(self.config_path, 'r') as f:
                config_content = f.read()
            
            # Check if config has changed
            current_hash = hashlib.sha256(config_content.encode()).hexdigest()
            
            if current_hash == self.config_hash and self.config_cache:
                logger.info(f"📋 Using cached config from {self.config_path}")
                return self.config_cache
            
            # Parse new config
            config = json.loads(config_content)
            
            # Validate config
            validated_config = self._validate_config(config)
            
            # Cache the config
            self.config_cache = validated_config
            self.config_hash = current_hash
            
            logger.info(f"✅ Loaded and validated config from {self.config_path}")
            return validated_config
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in {self.config_path}: {e}")
            logger.info("📋 Using default config")
            return self.default_config
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            logger.info("📋 Using default config")
            return self.default_config
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance configuration."""
        # Start with default config
        validated_config = self.default_config.copy()
        
        # Update with loaded config
        if 'governance' in config:
            validated_config['governance'].update(config['governance'])
        
        if 'mcpServers' in config:
            validated_config['mcpServers'] = config['mcpServers']
        
        # Validate governance settings
        governance = validated_config['governance']
        
        # Validate deployment mode
        valid_modes = ['unified', 'multi-port', 'hybrid']
        if governance['deployment_mode'] not in valid_modes:
            logger.warning(f"⚠️ Invalid deployment mode: {governance['deployment_mode']}, using 'unified'")
            governance['deployment_mode'] = 'unified'
        
        # Validate transformation strategy
        valid_strategies = ['fastmcp_native', 'custom_wrapper']
        if governance.get('transformation_strategy', 'fastmcp_native') not in valid_strategies:
            logger.warning(f"⚠️ Invalid transformation strategy, using 'fastmcp_native'")
            governance['transformation_strategy'] = 'fastmcp_native'
        
        # Validate ports
        base_port = governance.get('base_port', 8173)
        if not isinstance(base_port, int) or base_port < 1024 or base_port > 65535:
            logger.warning(f"⚠️ Invalid base port: {base_port}, using 8173")
            governance['base_port'] = 8173
        
        # Validate MongoDB URI
        mongodb_uri = governance.get('mongodb_uri')
        if not mongodb_uri or not isinstance(mongodb_uri, str):
            logger.warning("⚠️ Invalid or missing MongoDB URI, using default")
            governance['mongodb_uri'] = "mongodb://localhost:27017"
        
        # Validate MCP servers
        validated_servers = {}
        for server_name, server_config in validated_config['mcpServers'].items():
            validated_server = self._validate_server_config(server_name, server_config)
            if validated_server:
                validated_servers[server_name] = validated_server
        
        validated_config['mcpServers'] = validated_servers
        
        logger.info(f"✅ Configuration validated: {len(validated_servers)} servers configured")
        
        return validated_config
    
    def _validate_server_config(self, server_name: str, server_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate individual server configuration with new governance options."""
        try:
            # Required fields
            if 'transport' not in server_config:
                logger.warning(f"⚠️ Server {server_name}: missing transport, skipping")
                return None
            
            transport = server_config['transport']
            
            # Validate transport-specific config
            if transport == 'stdio':
                if 'command' not in server_config:
                    logger.warning(f"⚠️ Server {server_name}: stdio transport missing command, skipping")
                    return None
                
                if 'args' not in server_config:
                    server_config['args'] = []
                
                if 'env' not in server_config:
                    server_config['env'] = {}
            
            elif transport in ['streamable-http', 'http']:
                if 'url' not in server_config:
                    logger.warning(f"⚠️ Server {server_name}: HTTP transport missing URL, skipping")
                    return None
                
                url = server_config['url']
                if not url.startswith(('http://', 'https://')):
                    logger.warning(f"⚠️ Server {server_name}: invalid URL format, skipping")
                    return None
            
            else:
                logger.warning(f"⚠️ Server {server_name}: unsupported transport '{transport}', skipping")
                return None
            
            # Validate governance config with new options
            if 'governance' not in server_config:
                server_config['governance'] = {}
            
            governance = server_config['governance']
            
            # Set default governance mode
            if 'mode' not in governance:
                governance['mode'] = 'unified'
            
            # Validate mode
            valid_governance_modes = ['unified', 'separate_port']
            if governance['mode'] not in valid_governance_modes:
                logger.warning(f"⚠️ Server {server_name}: invalid governance mode, using 'unified'")
                governance['mode'] = 'unified'
            
            # Validate rate limit
            if 'rate_limit' in governance:
                rate_limit = governance['rate_limit']
                if not isinstance(rate_limit, int) or rate_limit < 1:
                    logger.warning(f"⚠️ Server {server_name}: invalid rate limit, using default")
                    governance['rate_limit'] = 100
            else:
                governance['rate_limit'] = 100
            
            # NEW: Validate transformation options
            if 'hide_original_tools' not in governance:
                governance['hide_original_tools'] = True
            
            if 'governance_prefix' not in governance:
                governance['governance_prefix'] = 'governed_'
            
            if 'detailed_tracking' not in governance:
                governance['detailed_tracking'] = True
            
            # Validate security level
            valid_security_levels = ['low', 'medium', 'high']
            if governance.get('security_level', 'medium') not in valid_security_levels:
                logger.warning(f"⚠️ Server {server_name}: invalid security level, using 'medium'")
                governance['security_level'] = 'medium'
            
            # Validate port for separate_port mode
            if governance['mode'] == 'separate_port':
                if 'port' not in governance:
                    logger.warning(f"⚠️ Server {server_name}: separate_port mode missing port, using 8174")
                    governance['port'] = 8174
                else:
                    port = governance['port']
                    if not isinstance(port, int) or port < 1024 or port > 65535:
                        logger.warning(f"⚠️ Server {server_name}: invalid port {port}, using 8174")
                        governance['port'] = 8174
            
            # Validate allowed hours
            if 'allowed_hours' in governance:
                allowed_hours = governance['allowed_hours']
                if not isinstance(allowed_hours, list) or not all(isinstance(h, int) and 0 <= h <= 23 for h in allowed_hours):
                    logger.warning(f"⚠️ Server {server_name}: invalid allowed_hours, using all hours")
                    governance['allowed_hours'] = list(range(24))
            
            logger.info(f"✅ Server {server_name} configuration validated")
            return server_config
            
        except Exception as e:
            logger.error(f"❌ Error validating server {server_name}: {e}")
            return None
    
    def get_server_count_by_mode(self, config: Dict[str, Any]) -> Dict[str, int]:
        """Get server count by deployment mode."""
        mode_counts = {'unified': 0, 'separate_port': 0}
        
        for server_config in config.get('mcpServers', {}).values():
            mode = server_config.get('governance', {}).get('mode', 'unified')
            if mode in mode_counts:
                mode_counts[mode] += 1
        
        return mode_counts
    
    def validate_port_conflicts(self, config: Dict[str, Any]) -> List[str]:
        """Check for port conflicts in configuration."""
        conflicts = []
        used_ports = {}
        
        # Check base port
        base_port = config.get('governance', {}).get('base_port', 8173)
        used_ports['unified'] = base_port
        
        for server_name, server_config in config.get('mcpServers', {}).items():
            governance = server_config.get('governance', {})
            if governance.get('mode') == 'separate_port':
                port = governance.get('port', 8174)
                if port in used_ports.values():
                    conflicts.append(f"Port {port} conflict: {server_name}")
                else:
                    used_ports[server_name] = port
        
        return conflicts