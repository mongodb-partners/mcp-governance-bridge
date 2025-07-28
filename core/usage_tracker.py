# core/usage_tracker.py
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import uuid
from utils.logger import logger

class UsageTracker:
    """Tracks usage of MCP tools and servers with enhanced metadata support."""
    
    def __init__(self, mongodb_client):
        self.mongodb_client = mongodb_client
        self.active_sessions = {}  # In-memory session tracking
        self.metrics_cache = {}
        self.cache_expiry = 300  # 5 minutes
        
    async def start_tracking(self, server_name: str, tool_name: str, 
                           parameters: Dict[str, Any], user_id: str = "system",
                           extra_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start tracking a tool usage session with optional extra metadata."""
        session_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "server_name": server_name,
            "tool_name": tool_name,
            "user_id": user_id,
            "parameters": parameters,
            "start_time": datetime.now(timezone.utc),
            "status": "started",
            "client_ip": "localhost",
            "extra_metadata": extra_metadata or {}
        }
        
        # Store in memory for quick access
        self.active_sessions[session_id] = session_data
        
        # Store in MongoDB
        await self.mongodb_client.store_usage_session(session_data)
        
        logger.info(f"📊 Started tracking: {server_name}.{tool_name} (session: {session_id})")
        return session_id
    
    async def complete_tracking(self, session_id: str, result: Any, status: str,
                              duration_ms: float, error_message: Optional[str] = None,
                              extra_metadata: Optional[Dict[str, Any]] = None):
        """Complete tracking for a session with optional extra metadata."""
        if session_id not in self.active_sessions:
            logger.warning(f"⚠️ Session {session_id} not found in active sessions")
            return
        
        session_data = self.active_sessions[session_id]
        
        # Update session with completion data
        completion_data = {
            "session_id": session_id,
            "end_time": datetime.now(timezone.utc),
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error_message,
            "has_result": result is not None,
            "result_type": type(result).__name__ if result else None,
            "completion_metadata": extra_metadata or {}
        }
        
        # Update in MongoDB
        await self.mongodb_client.complete_usage_session(completion_data)
        
        # Remove from active sessions
        del self.active_sessions[session_id]
        
        logger.info(f"✅ Completed tracking: {session_data['server_name']}.{session_data['tool_name']} "
              f"({duration_ms:.1f}ms, {status})")
    
    async def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get usage metrics summary."""
        cache_key = f"metrics_{hours}h"
        now = datetime.now(timezone.utc)
        
        # Check cache
        if (cache_key in self.metrics_cache and 
            (now - self.metrics_cache[cache_key]["timestamp"]).seconds < self.cache_expiry):
            return self.metrics_cache[cache_key]["data"]
        
        try:
            # Get metrics from MongoDB
            metrics = await self.mongodb_client.get_usage_metrics(hours)
            
            # Enhance with real-time data
            enhanced_metrics = {
                "summary": metrics.get("summary", {}),
                "by_server": metrics.get("by_server", {}),
                "by_tool": metrics.get("by_tool", {}),
                "active_sessions": len(self.active_sessions),
                "cache_info": {
                    "cached_at": now.isoformat(),
                    "cache_duration_seconds": self.cache_expiry
                },
                "time_range": {
                    "hours": hours,
                    "from": (now - timedelta(hours=hours)).isoformat(),
                    "to": now.isoformat()
                }
            }
            
            # Cache the result
            self.metrics_cache[cache_key] = {
                "data": enhanced_metrics,
                "timestamp": now
            }
            
            return enhanced_metrics
            
        except Exception as e:
            logger.error(f"❌ Error getting metrics summary: {e}")
            return {
                "error": str(e),
                "active_sessions": len(self.active_sessions),
                "timestamp": now.isoformat()
            }
    
    async def get_server_usage(self, server_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get usage statistics for a specific server."""
        try:
            usage_data = await self.mongodb_client.get_server_usage(server_name, hours)
            
            # Add real-time active sessions for this server
            active_for_server = [
                session for session in self.active_sessions.values()
                if session["server_name"] == server_name
            ]
            
            usage_data["active_sessions"] = len(active_for_server)
            usage_data["active_tools"] = list(set(
                session["tool_name"] for session in active_for_server
            ))
            
            return usage_data
            
        except Exception as e:
            logger.error(f"❌ Error getting server usage: {e}")
            return {"error": str(e)}
    
    async def get_tool_usage(self, server_name: str, tool_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get usage statistics for a specific tool."""
        try:
            return await self.mongodb_client.get_tool_usage(server_name, tool_name, hours)
        except Exception as e:
            logger.error(f"❌ Error getting tool usage: {e}")
            return {"error": str(e)}
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get currently active sessions."""
        active = []
        for session_id, session_data in self.active_sessions.items():
            # Calculate duration
            duration_seconds = (datetime.now(timezone.utc) - session_data["start_time"]).total_seconds()
            
            active_session = {
                "session_id": session_id,
                "server_name": session_data["server_name"],
                "tool_name": session_data["tool_name"],
                "user_id": session_data["user_id"],
                "start_time": session_data["start_time"].isoformat(),
                "duration_seconds": duration_seconds,
                "status": session_data["status"],
                "has_metadata": bool(session_data.get("extra_metadata"))
            }
            active.append(active_session)
        
        return active
    
    async def cleanup_stale_sessions(self, max_duration_hours: int = 1):
        """Clean up sessions that have been running too long."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_duration_hours)
        stale_sessions = []
        
        for session_id, session_data in list(self.active_sessions.items()):
            if session_data["start_time"] < cutoff_time:
                stale_sessions.append(session_id)
                
                # Mark as timed out
                await self.complete_tracking(
                    session_id, None, "timeout",
                    (datetime.now(timezone.utc) - session_data["start_time"]).total_seconds() * 1000,
                    "Session exceeded maximum duration"
                )
        
        if stale_sessions:
            logger.info(f"🧹 Cleaned up {len(stale_sessions)} stale sessions")
        
        return len(stale_sessions)
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time statistics."""
        if not self.active_sessions:
            return {
                "active_sessions": 0,
                "active_servers": 0,
                "active_tools": 0
            }
        
        active_servers = set(session["server_name"] for session in self.active_sessions.values())
        active_tools = set(f"{session['server_name']}.{session['tool_name']}" 
                          for session in self.active_sessions.values())
        
        return {
            "active_sessions": len(self.active_sessions),
            "active_servers": len(active_servers),
            "active_tools": len(active_tools),
            "servers": list(active_servers),
            "tools": list(active_tools)
        }