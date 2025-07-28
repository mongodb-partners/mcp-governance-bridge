# tests/conftest.py
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import tempfile
import json

# Add the parent directory to the path so we can import our modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.atlas_client import MongoDBAtlasClient
from core.governance_engine import GovernanceEngine
from core.usage_tracker import UsageTracker
from app.governance_server_manager import MCPGovernanceManager
from utils.config_loader import ConfigLoader

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_mongodb_client():
    """Mock MongoDB client for testing."""
    client = AsyncMock(spec=MongoDBAtlasClient)
    
    # Mock common database operations
    client.store_governance_log.return_value = True
    client.store_tool_log.return_value = True
    client.store_server_info.return_value = True
    client.get_server_list.return_value = [
        {
            "server_name": "test-server",
            "transport": "stdio",
            "governance_mode": "unified",
            "is_active": True,
            "registered_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    client.get_usage_metrics.return_value = {
        "summary": {
            "total_sessions": 10,
            "successful_sessions": 8,
            "failed_sessions": 2,
            "success_rate": 80.0,
            "avg_duration_ms": 150.5,
            "unique_servers": 2,
            "unique_tools": 5
        },
        "servers": ["test-server", "another-server"],
        "tools": ["tool1", "tool2", "tool3"]
    }
    client.get_tool_analytics.return_value = {
        "summary": {
            "total_unique_tools": 3,
            "total_calls": 15,
            "total_successful": 12,
            "total_failed": 2,
            "total_denied": 1,
            "overall_success_rate": 80.0
        },
        "tools": [
            {
                "server_name": "test-server",
                "tool_name": "test-tool",
                "total_calls": 10,
                "successful_calls": 8,
                "failed_calls": 2,
                "denied_calls": 0,
                "success_rate": 80.0,
                "avg_duration_ms": 120.0,
                "max_duration_ms": 200.0,
                "min_duration_ms": 50.0,
                "avg_output_size": 1024
            }
        ]
    }
    client.get_governance_violations.return_value = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_name": "test-server",
            "tool_name": "blocked-tool",
            "policy_violation": "rate_limit",
            "reason": "Rate limit exceeded",
            "session_id": "test-session-123"
        }
    ]
    
    return client

@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "governance": {
            "deployment_mode": "unified",
            "base_port": 8173,
            "enable_tracking": True,
            "enable_dashboard": True,
            "mongodb_uri": "mongodb://localhost:27017/test",
            "auth_disabled": True,
            "transformation_strategy": "fastmcp_native"
        },
        "mcpServers": {
            "test-server": {
                "transport": "stdio",
                "command": "echo",
                "args": ["test"],
                "env": {},
                "governance": {
                    "mode": "unified",
                    "rate_limit": 10,
                    "hide_original_tools": True,
                    "governance_prefix": "test_",
                    "detailed_tracking": True,
                    "enable_tool_logging": True,
                    "security_level": "medium",
                    "allowed_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17]
                }
            }
        }
    }

@pytest.fixture
def temp_config_file(test_config):
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass