# tests/test_usage_tracker.py
import pytest
from datetime import datetime, timezone
from core.usage_tracker import UsageTracker
from unittest.mock import AsyncMock, patch

class TestUsageTracker:
    """Test cases for the UsageTracker class."""
    
    @pytest.fixture
    def usage_tracker(self, mock_mongodb_client):
        """Create a usage tracker instance for testing."""
        # Mock the store_usage_session method
        mock_mongodb_client.store_usage_session = AsyncMock(return_value=True)
        mock_mongodb_client.complete_usage_session = AsyncMock(return_value=True)
        return UsageTracker(mock_mongodb_client)
    
    @pytest.mark.asyncio
    async def test_start_tracking(self, usage_tracker):
        """Test starting a tracking session."""
        session_id = await usage_tracker.start_tracking(
            "test-server", 
            "test-tool", 
            {"param1": "value1"},
            "test-user"
        )
        
        assert session_id is not None
        assert len(session_id) > 0
        assert session_id in usage_tracker.active_sessions
        
        session_data = usage_tracker.active_sessions[session_id]
        assert session_data["server_name"] == "test-server"
        assert session_data["tool_name"] == "test-tool"
        assert session_data["user_id"] == "test-user"
        assert session_data["status"] == "started"
    
    @pytest.mark.asyncio
    async def test_complete_tracking(self, usage_tracker):
        """Test completing a tracking session."""
        # Start a session first
        session_id = await usage_tracker.start_tracking(
            "test-server", "test-tool", {}, "test-user"
        )
        
        assert session_id in usage_tracker.active_sessions
        
        # Complete the session
        await usage_tracker.complete_tracking(
            session_id, 
            {"result": "success"}, 
            "success", 
            150.0
        )
        
        # Session should be removed from active sessions
        assert session_id not in usage_tracker.active_sessions
    
    @pytest.mark.asyncio
    async def test_complete_tracking_with_error(self, usage_tracker):
        """Test completing a tracking session with error."""
        session_id = await usage_tracker.start_tracking(
            "test-server", "test-tool", {}, "test-user"
        )
        
        await usage_tracker.complete_tracking(
            session_id, 
            None, 
            "error", 
            100.0,
            "Test error message"
        )
        
        assert session_id not in usage_tracker.active_sessions
    
    @pytest.mark.asyncio
    async def test_get_metrics_summary(self, usage_tracker):
        """Test getting metrics summary."""
        metrics = await usage_tracker.get_metrics_summary(24)
        
        assert "summary" in metrics
        assert "active_sessions" in metrics
        assert "cache_info" in metrics
        assert "time_range" in metrics
        
        # Check summary fields
        summary = metrics["summary"]
        assert "total_sessions" in summary
        assert "successful_sessions" in summary
        assert "failed_sessions" in summary
        assert "success_rate" in summary
    
    @pytest.mark.asyncio
    async def test_get_active_sessions(self, usage_tracker):
        """Test getting active sessions."""
        # Start a couple of sessions
        session1 = await usage_tracker.start_tracking(
            "server1", "tool1", {}, "user1"
        )
        session2 = await usage_tracker.start_tracking(
            "server2", "tool2", {}, "user2"
        )
        
        active_sessions = await usage_tracker.get_active_sessions()
        
        assert len(active_sessions) == 2
        session_ids = [s["session_id"] for s in active_sessions]
        assert session1 in session_ids
        assert session2 in session_ids
        
        # Check session structure
        for session in active_sessions:
            assert "session_id" in session
            assert "server_name" in session
            assert "tool_name" in session
            assert "user_id" in session
            assert "start_time" in session
            assert "duration_seconds" in session
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(self, usage_tracker):
        """Test cleaning up stale sessions."""
        # Start a session
        session_id = await usage_tracker.start_tracking(
            "test-server", "test-tool", {}, "test-user"
        )
        
        # Manually set start time to be old (simulate stale session)
        usage_tracker.active_sessions[session_id]["start_time"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        
        cleaned_count = await usage_tracker.cleanup_stale_sessions(max_duration_hours=1)
        
        assert cleaned_count == 1
        assert session_id not in usage_tracker.active_sessions
    
    def test_get_real_time_stats(self, usage_tracker):
        """Test getting real-time statistics."""
        # Add some active sessions manually
        usage_tracker.active_sessions = {
            "session1": {"server_name": "server1", "tool_name": "tool1"},
            "session2": {"server_name": "server2", "tool_name": "tool2"},
            "session3": {"server_name": "server1", "tool_name": "tool3"}
        }
        
        stats = usage_tracker.get_real_time_stats()
        
        assert stats["active_sessions"] == 3
        assert stats["active_servers"] == 2  # server1 and server2
        assert stats["active_tools"] == 3
        assert "server1" in stats["servers"]
        assert "server2" in stats["servers"]