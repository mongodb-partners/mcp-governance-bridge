# app/main.py
import asyncio
import signal
import sys
import atexit
from app.governance_server_manager import MCPGovernanceManager
from utils.logger import logger

class MCPGovernanceApp:
    """Main application for MCP Governance Bridge."""
    
    def __init__(self):
        self.manager = None
        self.dashboard_process = None
        self.shutdown_requested = False
        
        # Register cleanup on exit
        atexit.register(self.cleanup)
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"\n🛑 Received signal {signum}")
            self.shutdown_requested = True
            
            # Create new event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Schedule cleanup
            if loop.is_running():
                asyncio.create_task(self.shutdown())
            else:
                loop.run_until_complete(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("🛑 Initiating graceful shutdown...")
        
        if self.manager:
            await self.manager.stop_servers()
        
    
    def cleanup(self):
        """Cleanup on exit."""
        if not self.shutdown_requested:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.shutdown())
                loop.close()
            except:
                pass  # Best effort cleanup
    
    async def run(self):
        """Main application runner."""
        logger.info("🚀 Starting MCP Governance Bridge...")

        # Setup signal handlers
        self.setup_signal_handlers()
        
        try:
            # Initialize manager
            self.manager = MCPGovernanceManager()
            
            # Setup servers
            await self.manager.setup_all_servers()
          
            # Run servers (this will block until shutdown)
            await self.manager.run_servers()


                
        except KeyboardInterrupt:
            logger.info("🛑 Application interrupted by user")
        except Exception as e:
            logger.error(f"❌ Application error: {e}")
            import traceback
            traceback.logger.info_exc()
        finally:
            await self.shutdown()
            logger.info("👋 MCP Governance Bridge stopped")

def main():
    """Entry point for the application."""
    # Set up event loop policy for Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    app = MCPGovernanceApp()
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("\n🛑 Application interrupted")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()