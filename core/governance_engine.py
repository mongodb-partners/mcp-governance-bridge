# core/governance_engine.py
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import re
from utils.logger import logger

class GovernanceEngine:
    """Handles governance policies and enforcement."""
    
    def __init__(self, mongodb_client):
        self.mongodb_client = mongodb_client
        self.rate_limiters = {}  # In-memory rate limiting
        self.security_policies = {}
        self.load_default_policies()
    
    def load_default_policies(self):
        """Load default governance policies."""
        self.security_policies = {
            "default": {
                "max_requests_per_minute": 100,
                "max_concurrent_sessions": 10,
                "allowed_hours": list(range(24)),  # All hours by default
                "blocked_patterns": [
                    r"(password|secret|token|key)\s*[:=]\s*\w+",
                    r"(rm|del|delete)\s+-rf",
                    r"drop\s+table",
                    r"eval\s*\(",
                    r"exec\s*\("
                ],
                "high_security_mode": False
            }
        }
    
    async def check_governance(self, server_name: str, tool_name: str, 
                             parameters: Dict[str, Any], governance_config: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a tool call is allowed based on governance policies."""
        try:
            # Get or create policy for this server
            policy = self._get_server_policy(server_name, governance_config)
            
            # Check time-based restrictions
            time_check = await self._check_time_restrictions(policy)
            if not time_check["allowed"]:
                return time_check
            
            # Check rate limiting
            rate_check = await self._check_rate_limit(server_name, policy)
            if not rate_check["allowed"]:
                return rate_check
            
            # Check security patterns
            security_check = await self._check_security_patterns(parameters, policy)
            if not security_check["allowed"]:
                return security_check
            
            # Check high security mode restrictions
            if policy.get("high_security_mode", False):
                security_mode_check = await self._check_high_security_restrictions(
                    server_name, tool_name, parameters
                )
                if not security_mode_check["allowed"]:
                    return security_mode_check
            
            # Log governance decision
            await self._log_governance_decision(server_name, tool_name, "allowed", policy)
            
            return {
                "allowed": True,
                "reason": "Governance checks passed",
                "policy_applied": policy
            }
            
        except Exception as e:
            logger.error(f"❌ Governance check error: {e}")
            return {
                "allowed": False,
                "reason": f"Governance error: {str(e)}",
                "error": True
            }
    
    def _get_server_policy(self, server_name: str, governance_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get governance policy for a server."""
        # Start with default policy
        policy = self.security_policies["default"].copy()
        
        # Override with server-specific config
        if "rate_limit" in governance_config:
            policy["max_requests_per_minute"] = governance_config["rate_limit"]
        
        if "allowed_hours" in governance_config:
            policy["allowed_hours"] = governance_config["allowed_hours"]
        
        if "high_security" in governance_config:
            policy["high_security_mode"] = governance_config["high_security"]
        
        return policy
    
    async def _check_time_restrictions(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Check if current time is allowed."""
        current_hour = datetime.now().hour
        allowed_hours = policy.get("allowed_hours", list(range(24)))
        print(f"Current hour: {current_hour}, Allowed hours: {allowed_hours}")
        if current_hour not in allowed_hours:
            return {
                "allowed": False,
                "reason": f"Access not allowed at hour {current_hour}. Allowed hours: {allowed_hours}",
                "policy_violation": "time_restriction"
            }
        
        return {"allowed": True}
    
    async def _check_rate_limit(self, server_name: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Check rate limiting for server."""
        max_requests = policy.get("max_requests_per_minute", 100)
        current_time = datetime.now(timezone.utc)
        
        # Initialize rate limiter if not exists
        if server_name not in self.rate_limiters:
            self.rate_limiters[server_name] = {
                "requests": [],
                "window_start": current_time
            }
        
        rate_limiter = self.rate_limiters[server_name]
        
        # Clean old requests (older than 1 minute)
        cutoff_time = current_time - timedelta(minutes=1)
        rate_limiter["requests"] = [
            req_time for req_time in rate_limiter["requests"] 
            if req_time > cutoff_time
        ]
        
        # Check if limit exceeded
        if len(rate_limiter["requests"]) >= max_requests:
            return {
                "allowed": False,
                "reason": f"Rate limit exceeded: {len(rate_limiter['requests'])}/{max_requests} requests per minute",
                "policy_violation": "rate_limit"
            }
        
        # Add current request
        rate_limiter["requests"].append(current_time)
        print(f"Rate limiter for {server_name}: {len(rate_limiter['requests'])} requests in the last minute")
        return {
            "allowed": True,
            "remaining_requests": max_requests - len(rate_limiter["requests"])
        }
    
    async def _check_security_patterns(self, parameters: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
        """Check for security-sensitive patterns in parameters."""
        blocked_patterns = policy.get("blocked_patterns", [])
        print(f"Checking parameters: {parameters} against patterns: {blocked_patterns}")
        if not blocked_patterns:
            return {"allowed": True}
        
        # Convert parameters to searchable text
        param_text = str(parameters).lower()
        
        for pattern in blocked_patterns:
            if re.search(pattern, param_text, re.IGNORECASE):
                return {
                    "allowed": False,
                    "reason": f"Security pattern detected: {pattern}",
                    "policy_violation": "security_pattern",
                    "pattern": pattern
                }
        
        return {"allowed": True}
    
    async def _check_high_security_restrictions(self, server_name: str, tool_name: str, 
                                               parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Additional checks for high security mode."""
        # Check for sensitive operations
        sensitive_operations = ["delete", "remove", "drop", "truncate", "exec", "eval"]
        
        if any(op in tool_name.lower() for op in sensitive_operations):
            return {
                "allowed": False,
                "reason": f"High security mode: {tool_name} contains sensitive operation",
                "policy_violation": "high_security_sensitive_operation"
            }
        print(f"Checking parameters for high security mode: {parameters}")
        # Check parameter size
        param_str = str(parameters)
        if len(param_str) > 10000:  # 10KB limit
            return {
                "allowed": False,
                "reason": f"High security mode: Parameter size too large ({len(param_str)} chars)",
                "policy_violation": "high_security_parameter_size"
            }
        
        return {"allowed": True}
    
    async def _log_governance_decision(self, server_name: str, tool_name: str, 
                                     decision: str, policy: Dict[str, Any]):
        """Log governance decision to MongoDB."""
        log_entry = {
            "server_name": server_name,
            "tool_name": tool_name,
            "decision": decision,
            "policy_applied": policy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "governance_version": "1.0"
        }
        
        await self.mongodb_client.store_governance_log(log_entry)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get governance engine status."""
        active_rate_limiters = len(self.rate_limiters)
        
        # Calculate total requests in last minute across all servers
        current_time = datetime.now(timezone.utc)
        cutoff_time = current_time - timedelta(minutes=1)
        
        total_recent_requests = 0
        for server_name, rate_limiter in self.rate_limiters.items():
            recent_requests = [
                req_time for req_time in rate_limiter["requests"] 
                if req_time > cutoff_time
            ]
            total_recent_requests += len(recent_requests)
        
        return {
            "status": "active",
            "active_rate_limiters": active_rate_limiters,
            "total_requests_last_minute": total_recent_requests,
            "policies_loaded": len(self.security_policies),
            "default_policy": self.security_policies["default"],
            "timestamp": current_time.isoformat()
        }
    
    async def update_server_policy(self, server_name: str, policy_updates: Dict[str, Any]):
        """Update policy for a specific server."""
        if server_name not in self.security_policies:
            self.security_policies[server_name] = self.security_policies["default"].copy()
        
        self.security_policies[server_name].update(policy_updates)
        
        # Store in MongoDB
        policy_record = {
            "server_name": server_name,
            "policy": self.security_policies[server_name],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.mongodb_client.store_server_policy(policy_record)
        
        logger.info(f"✅ Updated policy for {server_name}")
    
    async def get_governance_violations(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get governance violations from the last N hours."""
        try:
            return await self.mongodb_client.get_governance_violations(hours)
        except Exception as e:
            logger.error(f"❌ Error getting governance violations: {e}")
            return []
    
    def clear_rate_limiters(self):
        """Clear all rate limiters (for testing/reset)."""
        self.rate_limiters.clear()
        logger.info("🧹 Rate limiters cleared")