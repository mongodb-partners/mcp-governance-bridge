# tests/test_main.py
import pytest
from unittest.mock import AsyncMock, patch, Mock
from app.main import MCPGovernanceApp

class TestMCPGovernanceApp:
    """Test cases for the main application."""
    
    @pytest.fixture
    def mock_governance_manager(self):
        """Mock governance manager."""
        manager = AsyncMock()
        manager.setup_all_servers = AsyncMock()
        manager.run_servers = AsyncMock()
        manager.stop_servers = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_app_initialization(self):
        """Test application initialization."""
        app = MCPGovernanceApp()
        
        assert app.manager is None
        assert app.dashboard_process is None
        assert app.shutdown_requested is False
    
    @pytest.mark.asyncio
    async def test_app_shutdown(self, mock_governance_manager):
        """Test graceful shutdown."""
        app = MCPGovernanceApp()
        app.manager = mock_governance_manager
        
        await app.shutdown()
        
        mock_governance_manager.stop_servers.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.main.MCPGovernanceManager')
    async def test_app_run_success(self, mock_manager_class, mock_governance_manager):
        """Test successful application run."""
        mock_manager_class.return_value = mock_governance_manager
        
        app = MCPGovernanceApp()
        
        # Mock the run to complete immediately
        async def mock_run():
            app.shutdown_requested = True
        
        with patch.object(app, 'setup_signal_handlers'):
            mock_governance_manager.run_servers.side_effect = mock_run
            
            await app.run()
            
            mock_governance_manager.setup_all_servers.assert_called_once()
            mock_governance_manager.run_servers.assert_called_once()