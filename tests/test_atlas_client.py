# tests/test_atlas_client.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from database.atlas_client import MongoDBAtlasClient
from datetime import datetime, timezone

class TestMongoDBAtlasClient:
    """Test cases for the MongoDBAtlasClient class."""
    
    @pytest.fixture
    def mock_mongo_client(self):
        """Mock MongoDB client."""
        with patch('database.atlas_client.MongoClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            # Mock database and collection operations
            mock_db = Mock()
            mock_instance.__getitem__ = Mock(return_value=mock_db)
            mock_instance.admin.command = Mock(return_value={'ok': 1})
            
            # Mock collections
            mock_collection = Mock()
            mock_db.__getitem__ = Mock(return_value=mock_collection)
            mock_collection.create_index = Mock()
            mock_collection.insert_one = Mock(return_value=Mock(acknowledged=True))
            mock_collection.find = Mock(return_value=[])
            mock_collection.aggregate = Mock(return_value=[])
            
            yield mock_instance
    
    @pytest.mark.asyncio
    @patch.dict('os.environ', {'MONGODB_URI': 'mongodb://test:27017'})
    async def test_client_initialization(self, mock_mongo_client):
        """Test MongoDB client initialization."""
        with patch('database.atlas_client.MongoClient'):
            client = MongoDBAtlasClient()
            assert client.database_name == "mcp_governance"
    
    @pytest.mark.asyncio
    async def test_store_tool_log(self, mock_mongodb_client):
        """Test storing tool log."""
        log_entry = {
            "session_id": "test-session",
            "server_name": "test-server",
            "tool_name": "test-tool",
            "timestamp": datetime.now(timezone.utc),
            "status": "success"
        }
        
        result = await mock_mongodb_client.store_tool_log(log_entry)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_usage_metrics(self, mock_mongodb_client):
        """Test getting usage metrics."""
        metrics = await mock_mongodb_client.get_usage_metrics(24)
        
        assert "summary" in metrics
        assert "servers" in metrics
        assert "tools" in metrics
        
        summary = metrics["summary"]
        assert "total_sessions" in summary
        assert "success_rate" in summary
    
    @pytest.mark.asyncio
    async def test_get_tool_analytics(self, mock_mongodb_client):
        """Test getting tool analytics."""
        analytics = await mock_mongodb_client.get_tool_analytics(hours=24)
        
        assert "summary" in analytics
        assert "tools" in analytics
        
        if analytics["tools"]:
            tool = analytics["tools"][0]
            assert "server_name" in tool
            assert "tool_name" in tool
            assert "total_calls" in tool
            assert "success_rate" in tool
    
    @pytest.mark.asyncio
    async def test_get_governance_violations(self, mock_mongodb_client):
        """Test getting governance violations."""
        violations = await mock_mongodb_client.get_governance_violations(24)
        
        assert isinstance(violations, list)
        if violations:
            violation = violations[0]
            assert "timestamp" in violation
            assert "server_name" in violation
            assert "policy_violation" in violation
    
    @pytest.mark.asyncio
    async def test_store_server_info(self, mock_mongodb_client):
        """Test storing server information."""
        server_info = {
            "server_name": "test-server",
            "transport": "stdio",
            "governance_mode": "unified",
            "is_active": True
        }
        
        result = await mock_mongodb_client.store_server_info(server_info)
        assert result is True