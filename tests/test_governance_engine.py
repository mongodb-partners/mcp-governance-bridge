# tests/test_governance_engine.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from core.governance_engine import GovernanceEngine

class TestGovernanceEngine:
    """Test cases for the GovernanceEngine class."""
    
    @pytest.fixture
    def governance_engine(self, mock_mongodb_client):
        """Create a governance engine instance for testing."""
        return GovernanceEngine(mock_mongodb_client)
    
    @pytest.mark.asyncio
    async def test_governance_engine_initialization(self, governance_engine):
        """Test governance engine initializes correctly."""
        assert governance_engine.mongodb_client is not None
        assert governance_engine.rate_limiters == {}
        assert "default" in governance_engine.security_policies
        
    @pytest.mark.asyncio
    async def test_check_governance_allowed(self, governance_engine):
        """Test governance check allows valid requests."""
        result = await governance_engine.check_governance(
            "test-server", 
            "test-tool", 
            {"param1": "value1"}, 
            {"rate_limit": 100, "allowed_hours": list(range(24))}
        )
        
        assert result["allowed"] is True
        assert "reason" in result
        assert "policy_applied" in result
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, governance_engine):
        """Test rate limiting functionality."""
        server_name = "test-server"
        governance_config = {"rate_limit": 2}
        
        # First two requests should be allowed
        for _ in range(2):
            result = await governance_engine.check_governance(
                server_name, "test-tool", {}, governance_config
            )
            assert result["allowed"] is True
        
        # Third request should be denied
        result = await governance_engine.check_governance(
            server_name, "test-tool", {}, governance_config
        )
        assert result["allowed"] is False
        assert "rate limit" in result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_time_restrictions(self, governance_engine):
        """Test time-based access restrictions."""
        # Mock current hour to be outside allowed hours
        with patch('core.governance_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 2  # 2 AM
            
            result = await governance_engine.check_governance(
                "test-server", 
                "test-tool", 
                {}, 
                {"allowed_hours": [9, 10, 11, 12, 13]}
            )
            
            assert result["allowed"] is False
            assert "hour" in result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_security_patterns(self, governance_engine):
        """Test security pattern detection."""
        # Test with suspicious parameters
        suspicious_params = {"sql": "DROP TABLE users;"}
        
        result = await governance_engine.check_governance(
            "test-server",
            "test-tool",
            suspicious_params,
            {"blocked_patterns": [r"drop\s+table"]}
        )
        
        assert result["allowed"] is False
        assert "security pattern" in result["reason"].lower()
    
    @pytest.mark.asyncio
    async def test_governance_status(self, governance_engine):
        """Test getting governance engine status."""
        status = await governance_engine.get_status()
        
        assert "status" in status
        assert "active_rate_limiters" in status
        assert "total_requests_last_minute" in status
        assert "policies_loaded" in status
        assert "timestamp" in status
    
    @pytest.mark.asyncio
    async def test_update_server_policy(self, governance_engine):
        """Test updating server-specific policies."""
        server_name = "test-server"
        policy_updates = {
            "max_requests_per_minute": 50,
            "high_security_mode": True
        }
        
        await governance_engine.update_server_policy(server_name, policy_updates)
        
        assert server_name in governance_engine.security_policies
        assert governance_engine.security_policies[server_name]["max_requests_per_minute"] == 50
        assert governance_engine.security_policies[server_name]["high_security_mode"] is True
    
    def test_clear_rate_limiters(self, governance_engine):
        """Test clearing rate limiters."""
        # Add some rate limiters
        governance_engine.rate_limiters["server1"] = {"requests": [], "window_start": datetime.now()}
        governance_engine.rate_limiters["server2"] = {"requests": [], "window_start": datetime.now()}
        
        assert len(governance_engine.rate_limiters) == 2
        
        governance_engine.clear_rate_limiters()
        
        assert len(governance_engine.rate_limiters) == 0