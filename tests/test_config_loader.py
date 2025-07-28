# tests/test_config_loader.py
import pytest
import json
import tempfile
import os
from utils.config_loader import ConfigLoader

class TestConfigLoader:
    """Test cases for the ConfigLoader class."""
    
    def test_load_default_config(self):
        """Test loading default configuration when file doesn't exist."""
        config_loader = ConfigLoader("nonexistent_config.json")
        config = config_loader.load_config()
        
        assert "governance" in config
        assert "mcpServers" in config
        assert config["governance"]["deployment_mode"] == "unified"
        assert config["governance"]["base_port"] == 8173
    
    def test_load_valid_config_file(self, temp_config_file):
        """Test loading a valid configuration file."""
        config_loader = ConfigLoader(temp_config_file)
        config = config_loader.load_config()
        
        assert config["governance"]["deployment_mode"] == "unified"
        assert "test-server" in config["mcpServers"]
        assert config["mcpServers"]["test-server"]["transport"] == "stdio"
    
    def test_load_invalid_json_file(self):
        """Test loading an invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            config_loader = ConfigLoader(temp_path)
            config = config_loader.load_config()
            
            # Should fall back to default config
            assert config["governance"]["deployment_mode"] == "unified"
        finally:
            os.unlink(temp_path)
    
    def test_validate_server_config(self, test_config):
        """Test server configuration validation."""
        config_loader = ConfigLoader()
        
        # Valid server config
        valid_server = {
            "transport": "stdio",
            "command": "echo",
            "args": ["test"],
            "governance": {
                "mode": "unified",
                "rate_limit": 100
            }
        }
        
        result = config_loader._validate_server_config("test-server", valid_server)
        assert result is not None
        assert result["transport"] == "stdio"
        assert result["governance"]["rate_limit"] == 100
    
    def test_validate_invalid_server_config(self):
        """Test validation of invalid server configuration."""
        config_loader = ConfigLoader()
        
        # Invalid server config (missing transport)
        invalid_server = {
            "command": "echo",
            "args": ["test"]
        }
        
        result = config_loader._validate_server_config("invalid-server", invalid_server)
        assert result is None
    
    def test_get_server_count_by_mode(self, test_config):
        """Test getting server count by mode."""
        config_loader = ConfigLoader()
        mode_counts = config_loader.get_server_count_by_mode(test_config)
        
        assert "unified" in mode_counts
        assert "separate_port" in mode_counts
        assert mode_counts["unified"] == 1  # test-server is in unified mode
    
    def test_validate_port_conflicts(self, test_config):
        """Test port conflict validation."""
        config_loader = ConfigLoader()
        conflicts = config_loader.validate_port_conflicts(test_config)
        
        # Should be no conflicts in the test config
        assert len(conflicts) == 0
    
    def test_config_caching(self, temp_config_file):
        """Test configuration caching."""
        config_loader = ConfigLoader(temp_config_file)
        
        # Load config first time
        config1 = config_loader.load_config()
        
        # Load config second time (should be cached)
        config2 = config_loader.load_config()
        
        assert config1 == config2
        assert config_loader.config_cache is not None