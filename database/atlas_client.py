# database/atlas_client.py
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure, OperationFailure
import json
from utils.logger import logger
from dotenv import load_dotenv

load_dotenv(override=True)

class MongoDBAtlasClient:
    """MongoDB Atlas client for governance data storage."""
    
    def __init__(self):
        # Get MongoDB URI from config or environment
        self.uri = os.getenv("MONGODB_URI")
        if not self.uri:
            # Fallback to config file
            try:
                with open("mcp_governance_config.json", 'r') as f:
                    config = json.load(f)
                    self.uri = config.get('governance', {}).get('mongodb_uri')
            except:
                pass
        
        if not self.uri:
            raise ValueError("MongoDB URI not found in environment or config")
            
        self.database_name = os.getenv("MONGODB_DATABASE", "mcp_governance")
        self.client = None
        self.database = None
        self._connect()
    
    def _connect(self):
        """Connect to MongoDB Atlas."""
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                retryWrites=True
            )
            
            # Test connection
            self.client.admin.command('ping')
            self.database = self.client[self.database_name]
            
            logger.info(f"✅ Connected to MongoDB: {self.database_name}")
            self._create_indexes()
            
        except ConnectionFailure as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ MongoDB connection error: {e}")
            raise
    
    def _create_indexes(self):
        """Create necessary indexes for performance."""
        try:
            # Server info indexes
            servers_collection = self.database["servers"]
            servers_collection.create_index([("server_name", ASCENDING)], unique=True)
            servers_collection.create_index([("is_active", ASCENDING)])
            
            # Governance logs indexes
            governance_collection = self.database["governance_logs"]
            governance_collection.create_index([("server_name", ASCENDING)])
            governance_collection.create_index([("timestamp", DESCENDING)])
            governance_collection.create_index([("decision", ASCENDING)])
            
            # Tools indexes
            tools_collection = self.database["server_tools"]
            tools_collection.create_index([("server_name", ASCENDING)])
            tools_collection.create_index([("tool_name", ASCENDING)])
            tools_collection.create_index([
                ("server_name", ASCENDING),
                ("tool_name", ASCENDING)
            ], unique=True)
            
            # Tool logs indexes
            tool_logs_collection = self.database["tool_logs"]
            tool_logs_collection.create_index([("session_id", ASCENDING)])
            tool_logs_collection.create_index([("server_name", ASCENDING)])
            tool_logs_collection.create_index([("tool_name", ASCENDING)])
            tool_logs_collection.create_index([("timestamp", DESCENDING)])
            tool_logs_collection.create_index([("event_type", ASCENDING)])
            tool_logs_collection.create_index([("status", ASCENDING)])
            tool_logs_collection.create_index([
                ("server_name", ASCENDING),
                ("tool_name", ASCENDING),
                ("timestamp", DESCENDING)
            ])
            
            logger.info("✅ MongoDB indexes created")
            
        except Exception as e:
            logger.error(f"⚠️ Failed to create some indexes: {e}")
    
    # Tool logging methods
    async def store_tool_log(self, log_entry: Dict[str, Any]) -> bool:
        """Store detailed tool execution log."""
        try:
            collection = self.database["tool_logs"]
            
            # Prepare document with serializable datetime objects
            document = {
                **log_entry,
                "start_time": log_entry.get("start_time").isoformat() if log_entry.get("start_time") else None,
                "end_time": log_entry.get("end_time").isoformat() if log_entry.get("end_time") else None,
                "timestamp": log_entry.get("timestamp").isoformat() if log_entry.get("timestamp") else datetime.now(timezone.utc).isoformat(),
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "document_type": "tool_log"
            }
            
            # Handle large inputs/outputs by truncating if needed
            max_content_size = 10000  # 10KB limit
            
            if "inputs" in document and document["inputs"] and document["inputs"] != {"_tracked": False}:
                inputs_str = json.dumps(document["inputs"], default=str)
                if len(inputs_str) > max_content_size:
                    document["inputs"] = {"_truncated": True, "_original_size": len(inputs_str)}
                    document["inputs_truncated"] = True
            
            if "outputs" in document and document["outputs"]:
                outputs_str = json.dumps(document["outputs"], default=str)
                if len(outputs_str) > max_content_size:
                    document["outputs"] = {"_truncated": True, "_original_size": len(outputs_str)}
                    document["outputs_truncated"] = True
            
            result = collection.insert_one(document)
            logger.debug(f"📝 Stored tool log: {document.get('server_name')}.{document.get('tool_name')}")
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"❌ Error storing tool log: {e}")
            return False

    async def get_tool_logs(self, server_name: str = None, tool_name: str = None, 
                          session_id: str = None, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve tool execution logs with filters."""
        try:
            collection = self.database["tool_logs"]
            
            # Build query
            query = {"document_type": "tool_log"}
            
            if server_name:
                query["server_name"] = server_name
            if tool_name:
                query["tool_name"] = tool_name
            if session_id:
                query["session_id"] = session_id
            
            # Time filter
            if hours > 0:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours)
                query["timestamp"] = {
                    "$gte": start_time.isoformat(),
                    "$lte": end_time.isoformat()
                }
            
            # Execute query
            logs = list(collection.find(
                query,
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit))
            
            return logs
            
        except Exception as e:
            logger.error(f"❌ Error retrieving tool logs: {e}")
            return []

    async def get_tool_analytics(self, server_name: str = None, hours: int = 24) -> Dict[str, Any]:
        """Get analytics data for tool usage."""
        try:
            collection = self.database["tool_logs"]
            
            # Build match query
            match_query = {
                "document_type": "tool_log",
                "event_type": "tool_completion"
            }
            
            if server_name:
                match_query["server_name"] = server_name
                
            # Time filter
            if hours > 0:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours)
                match_query["timestamp"] = {
                    "$gte": start_time.isoformat(),
                    "$lte": end_time.isoformat()
                }
            
            # Aggregation pipeline
            pipeline = [
                {"$match": match_query},
                {
                    "$group": {
                        "_id": {
                            "server_name": "$server_name",
                            "tool_name": "$tool_name"
                        },
                        "total_calls": {"$sum": 1},
                        "successful_calls": {
                            "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                        },
                        "failed_calls": {
                            "$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}
                        },
                        "denied_calls": {
                            "$sum": {"$cond": [{"$eq": ["$status", "denied"]}, 1, 0]}
                        },
                        "avg_duration_ms": {"$avg": "$duration_ms"},
                        "max_duration_ms": {"$max": "$duration_ms"},
                        "min_duration_ms": {"$min": "$duration_ms"},
                        "avg_output_size": {"$avg": "$output_size"}
                    }
                },
                {
                    "$project": {
                        "server_name": "$_id.server_name",
                        "tool_name": "$_id.tool_name",
                        "total_calls": 1,
                        "successful_calls": 1,
                        "failed_calls": 1,
                        "denied_calls": 1,
                        "success_rate": {
                            "$multiply": [
                                {"$divide": ["$successful_calls", "$total_calls"]},
                                100
                            ]
                        },
                        "avg_duration_ms": {"$round": ["$avg_duration_ms", 2]},
                        "max_duration_ms": 1,
                        "min_duration_ms": 1,
                        "avg_output_size": {"$round": ["$avg_output_size", 0]}
                    }
                },
                {"$sort": {"total_calls": -1}}
            ]
            
            results = list(collection.aggregate(pipeline))
            
            # Calculate summary statistics
            summary = {
                "total_unique_tools": len(results),
                "total_calls": sum(r["total_calls"] for r in results),
                "total_successful": sum(r["successful_calls"] for r in results),
                "total_failed": sum(r["failed_calls"] for r in results),
                "total_denied": sum(r["denied_calls"] for r in results),
                "overall_success_rate": 0,
                "most_used_tool": results[0] if results else None
            }
            
            if summary["total_calls"] > 0:
                summary["overall_success_rate"] = round(
                    (summary["total_successful"] / summary["total_calls"]) * 100, 2
                )
            
            return {
                "summary": summary,
                "tools": results,
                "time_range_hours": hours
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting tool analytics: {e}")
            return {"error": str(e)}

    async def get_usage_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get usage metrics from tool_logs collection."""
        try:
            # Get analytics and transform to match expected format
            analytics = await self.get_tool_analytics(hours=hours)
            
            summary = analytics.get('summary', {})
            tools = analytics.get('tools', [])
            
            # Extract unique servers and tools from the tools list  
            servers = list(set(tool['server_name'] for tool in tools))
            tool_names = [f"{tool['server_name']}.{tool['tool_name']}" for tool in tools]
            
            return {
                "summary": {
                    "total_sessions": summary.get('total_calls', 0),  # Map calls to sessions
                    "successful_sessions": summary.get('total_successful', 0),
                    "failed_sessions": summary.get('total_failed', 0),
                    "success_rate": summary.get('overall_success_rate', 0),
                    "avg_duration_ms": self._calculate_avg_duration(tools),
                    "unique_servers": len(servers),
                    "unique_tools": len(tools)
                },
                "servers": servers,
                "tools": tool_names
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting usage metrics: {e}")
            return {
                "summary": {
                    "total_sessions": 0,
                    "successful_sessions": 0,
                    "failed_sessions": 0,
                    "success_rate": 0,
                    "avg_duration_ms": 0,
                    "unique_servers": 0,
                    "unique_tools": 0
                },
                "servers": [],
                "tools": []
            }

    async def get_server_usage(self, server_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get usage statistics for a specific server from tool_logs."""
        try:
            # Get analytics for specific server
            analytics = await self.get_tool_analytics(server_name=server_name, hours=hours)
            tools = analytics.get('tools', [])
            
            # Transform tools data to match expected format
            tools_usage = []
            for tool in tools:
                tools_usage.append({
                    "_id": tool['tool_name'],  # Map tool_name to _id for compatibility
                    "usage_count": tool['total_calls'],
                    "avg_duration": tool['avg_duration_ms'],
                    "success_count": tool['successful_calls']
                })
            
            return {
                "server_name": server_name,
                "time_range_hours": hours,
                "tools": tools_usage,
                "total_tools": len(tools_usage),
                "total_usage": sum(tool['total_calls'] for tool in tools)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting server usage: {e}")
            return {"error": str(e)}

    async def get_tool_usage(self, server_name: str, tool_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get usage statistics for a specific tool from tool_logs."""
        try:
            collection = self.database["tool_logs"]
            
            # Build match query for specific tool
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            match_query = {
                "document_type": "tool_log",
                "event_type": "tool_completion",
                "server_name": server_name,
                "tool_name": tool_name,
                "timestamp": {
                    "$gte": start_time.isoformat(),
                    "$lte": end_time.isoformat()
                }
            }
            
            # Aggregation pipeline for this specific tool
            pipeline = [
                {"$match": match_query},
                {
                    "$group": {
                        "_id": None,
                        "usage_count": {"$sum": 1},
                        "success_count": {
                            "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                        },
                        "error_count": {
                            "$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}
                        },
                        "avg_duration": {"$avg": "$duration_ms"}
                    }
                }
            ]
            
            results = list(collection.aggregate(pipeline))
            
            if results:
                result = results[0]
                usage_count = result.get("usage_count", 0)
                success_count = result.get("success_count", 0)
                
                return {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "usage_count": usage_count,
                    "success_count": success_count,
                    "error_count": result.get("error_count", 0),
                    "success_rate": (success_count / max(usage_count, 1)) * 100,
                    "avg_duration_ms": result.get("avg_duration", 0)
                }
            else:
                return {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "usage_count": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "success_rate": 0,
                    "avg_duration_ms": 0
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting tool usage: {e}")
            return {"error": str(e)}

    async def get_governance_violations(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get governance violations from both governance_logs and tool_logs."""
        try:
            violations = []
            
            # Get time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # 1. Get denied decisions from governance_logs
            governance_collection = self.database["governance_logs"]
            governance_query = {
                "document_type": "governance_log",
                "decision": {"$ne": "allowed"},  # Not allowed = violation
                "timestamp": {
                    "$gte": start_time.isoformat(),
                    "$lte": end_time.isoformat()
                }
            }
            
            governance_violations = list(governance_collection.find(
                governance_query,
                {"_id": 0}
            ).sort("timestamp", DESCENDING))
            
            # Format governance violations
            for violation in governance_violations:
                violations.append({
                    "timestamp": violation.get("timestamp"),
                    "server_name": violation.get("server_name"),
                    "tool_name": violation.get("tool_name"),
                    "policy_violation": violation.get("decision", "denied"),
                    "reason": f"Governance denied: {violation.get('decision', 'Unknown reason')}",
                    "session_id": None,  # Governance logs don't have session_id
                    "source": "governance_log",
                    "policy_applied": violation.get("policy_applied", {}),
                    "governance_version": violation.get("governance_version")
                })
            
            # 2. Get denied calls from tool_logs (for additional context)
            tool_logs_collection = self.database["tool_logs"]
            tool_logs_query = {
                "document_type": "tool_log",
                "event_type": "tool_completion",
                "status": "denied",
                "timestamp": {
                    "$gte": start_time.isoformat(),
                    "$lte": end_time.isoformat()
                }
            }
            
            tool_violations = list(tool_logs_collection.find(
                tool_logs_query,
                {"_id": 0}
            ).sort("timestamp", DESCENDING))
            
            # Format tool log violations
            for violation in tool_violations:
                violations.append({
                    "timestamp": violation.get("timestamp"),
                    "server_name": violation.get("server_name"),
                    "tool_name": violation.get("tool_name"),
                    "policy_violation": "execution_denied",
                    "reason": violation.get("error_message", "Tool execution denied"),
                    "session_id": violation.get("session_id"),
                    "source": "tool_log",
                    "duration_ms": violation.get("duration_ms", 0),
                    "inputs": violation.get("inputs", {})
                })
            
            # Sort all violations by timestamp (newest first)
            violations.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return violations
            
        except Exception as e:
            logger.error(f"❌ Error getting governance violations: {e}")
            return []

    async def get_governance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive governance metrics from governance_logs."""
        try:
            collection = self.database["governance_logs"]
            
            # Get time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # Aggregation pipeline to get governance metrics
            pipeline = [
                {
                    "$match": {
                        "document_type": "governance_log",
                        "timestamp": {
                            "$gte": start_time.isoformat(),
                            "$lte": end_time.isoformat()
                        }
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_decisions": {"$sum": 1},
                        "allowed_decisions": {
                            "$sum": {"$cond": [{"$eq": ["$decision", "allowed"]}, 1, 0]}
                        },
                        "denied_decisions": {
                            "$sum": {"$cond": [{"$ne": ["$decision", "allowed"]}, 1, 0]}
                        },
                        "servers": {"$addToSet": "$server_name"},
                        "tools": {"$addToSet": "$tool_name"},
                        "decisions_by_type": {"$push": "$decision"}
                    }
                }
            ]
            
            results = list(collection.aggregate(pipeline))
            
            if results:
                result = results[0]
                total_decisions = result.get("total_decisions", 0)
                allowed_decisions = result.get("allowed_decisions", 0)
                denied_decisions = result.get("denied_decisions", 0)
                
                return {
                    "total_decisions": total_decisions,
                    "allowed_decisions": allowed_decisions,
                    "denied_decisions": denied_decisions,
                    "approval_rate": (allowed_decisions / max(total_decisions, 1)) * 100,
                    "denial_rate": (denied_decisions / max(total_decisions, 1)) * 100,
                    "unique_servers": len(result.get("servers", [])),
                    "unique_tools": len(result.get("tools", [])),
                    "servers": result.get("servers", []),
                    "tools": result.get("tools", []),
                    "time_range_hours": hours
                }
            else:
                return {
                    "total_decisions": 0,
                    "allowed_decisions": 0,
                    "denied_decisions": 0,
                    "approval_rate": 100.0,
                    "denial_rate": 0.0,
                    "unique_servers": 0,
                    "unique_tools": 0,
                    "servers": [],
                    "tools": [],
                    "time_range_hours": hours
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting governance metrics: {e}")
            return {"error": str(e)}

    async def get_governance_policy_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze governance policy applications and effectiveness."""
        try:
            collection = self.database["governance_logs"]
            
            # Get time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # Get all governance decisions
            logs = list(collection.find(
                {
                    "document_type": "governance_log",
                    "timestamp": {
                        "$gte": start_time.isoformat(),
                        "$lte": end_time.isoformat()
                    }
                },
                {"_id": 0}
            ).sort("timestamp", DESCENDING))
            
            # Analyze policy applications
            policy_stats = {
                "high_security_mode_usage": 0,
                "rate_limit_checks": 0,
                "time_restriction_checks": 0,
                "pattern_blocking_checks": 0,
                "total_policy_applications": len(logs)
            }
            
            server_policy_stats = {}
            decision_timeline = []
            
            for log in logs:
                server_name = log.get("server_name", "unknown")
                policy_applied = log.get("policy_applied", {})
                decision = log.get("decision", "unknown")
                timestamp = log.get("timestamp")
                
                # Track server-specific stats
                if server_name not in server_policy_stats:
                    server_policy_stats[server_name] = {
                        "total_checks": 0,
                        "allowed": 0,
                        "denied": 0,
                        "high_security": False
                    }
                
                server_policy_stats[server_name]["total_checks"] += 1
                if decision == "allowed":
                    server_policy_stats[server_name]["allowed"] += 1
                else:
                    server_policy_stats[server_name]["denied"] += 1
                
                # Analyze policy features
                if policy_applied.get("high_security_mode"):
                    policy_stats["high_security_mode_usage"] += 1
                    server_policy_stats[server_name]["high_security"] = True
                
                if policy_applied.get("max_requests_per_minute"):
                    policy_stats["rate_limit_checks"] += 1
                
                if policy_applied.get("allowed_hours"):
                    policy_stats["time_restriction_checks"] += 1
                
                if policy_applied.get("blocked_patterns"):
                    policy_stats["pattern_blocking_checks"] += 1
                
                # Timeline data
                decision_timeline.append({
                    "timestamp": timestamp,
                    "server_name": server_name,
                    "decision": decision,
                    "high_security": policy_applied.get("high_security_mode", False)
                })
            
            return {
                "policy_stats": policy_stats,
                "server_policy_stats": server_policy_stats,
                "decision_timeline": decision_timeline[:50],  # Last 50 decisions
                "time_range_hours": hours
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting governance policy analysis: {e}")
            return {"error": str(e)}

    async def get_governance_timeline(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get governance decision timeline."""
        try:
            collection = self.database["governance_logs"]
            
            # Get time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # Query for governance decisions
            query = {
                "document_type": "governance_log",
                "timestamp": {
                    "$gte": start_time.isoformat(),
                    "$lte": end_time.isoformat()
                }
            }
            
            # Get timeline data
            timeline = list(collection.find(
                query,
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit))
            
            return timeline
            
        except Exception as e:
            logger.error(f"❌ Error getting governance timeline: {e}")
            return []

    def _calculate_avg_duration(self, tools: List[Dict[str, Any]]) -> float:
        """Calculate weighted average duration across all tools."""
        if not tools:
            return 0.0
        
        total_duration = 0
        total_calls = 0
        
        for tool in tools:
            tool_duration = tool.get('avg_duration_ms', 0)
            tool_calls = tool.get('total_calls', 0)
            total_duration += tool_duration * tool_calls
            total_calls += tool_calls
        
        return total_duration / max(total_calls, 1)

    # Server management methods
    async def store_server_info(self, server_info: Dict[str, Any]) -> bool:
        """Store server information."""
        try:
            collection = self.database["servers"]
            
            document = {
                **server_info,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "document_type": "server_info"
            }
            
            result = collection.replace_one(
                {"server_name": server_info["server_name"]},
                document,
                upsert=True
            )
            
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"❌ Error storing server info: {e}")
            return False
    
    async def get_server_list(self) -> List[Dict[str, Any]]:
        """Get list of all servers."""
        try:
            collection = self.database["servers"]
            
            servers = list(collection.find(
                {"document_type": "server_info"},
                {"_id": 0}
            ).sort("server_name", ASCENDING))
            
            return servers
            
        except Exception as e:
            logger.error(f"❌ Error getting server list: {e}")
            return []
    
    async def store_server_tools(self, tools_info: List[Dict[str, Any]]) -> bool:
        """Store server tools information."""
        try:
            collection = self.database["server_tools"]
            
            # Prepare documents
            documents = []
            for tool_info in tools_info:
                document = {
                    **tool_info,
                    "stored_at": datetime.now(timezone.utc).isoformat(),
                    "document_type": "server_tool"
                }
                documents.append(document)
            
            if documents:
                # Use bulk write to handle duplicates
                from pymongo import ReplaceOne
                operations = [
                    ReplaceOne(
                        {"server_name": doc["server_name"], "tool_name": doc["tool_name"]},
                        doc,
                        upsert=True
                    )
                    for doc in documents
                ]
                
                result = collection.bulk_write(operations)
                return result.acknowledged
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing server tools: {e}")
            return False
    
    # Governance methods
    async def store_governance_log(self, log_entry: Dict[str, Any]) -> bool:
        """Store governance decision log."""
        try:
            collection = self.database["governance_logs"]
            
            document = {
                **log_entry,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "document_type": "governance_log"
            }
            
            result = collection.insert_one(document)
            logger.info(f"✅ Stored governance log: {log_entry.get('server_name', 'unknown')}.{log_entry.get('tool_name', 'unknown')}")
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"❌ Error storing governance log: {e}")
            return False
    
    async def store_governance_config(self, governance_info: Dict[str, Any]) -> bool:
        """Store governance configuration."""
        try:
            collection = self.database["governance_configs"]
            
            document = {
                **governance_info,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "document_type": "governance_config"
            }
            
            result = collection.replace_one(
                {"server_name": governance_info["server_name"]},
                document,
                upsert=True
            )
            
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"❌ Error storing governance config: {e}")
            return False

    async def get_governance_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get governance configuration for a specific server."""
        try:
            collection = self.database["governance_configs"]
            
            document = collection.find_one({
                "server_name": server_name,
                "document_type": "governance_config"
            })
            
            if document:
                # Remove MongoDB's _id field from the result
                document.pop("_id", None)
                print(f"Retrieved governance config for {server_name}: {document}")
                return document
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error retrieving governance config for {server_name}: {e}")
            return None    
        
    async def store_server_policy(self, policy_record: Dict[str, Any]) -> bool:
        """Store server policy."""
        try:
            collection = self.database["server_policies"]
            
            document = {
                **policy_record,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "document_type": "server_policy"
            }
            
            result = collection.replace_one(
                {"server_name": policy_record["server_name"]},
                document,
                upsert=True
            )
            
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"❌ Error storing server policy: {e}")
            return False
    
    # Deployment methods
    async def store_deployment_info(self, deployment_info: Dict[str, Any]) -> bool:
        """Store deployment information."""
        try:
            collection = self.database["deployments"]
            
            document = {
                **deployment_info,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "document_type": "deployment_info"
            }
            
            result = collection.replace_one(
                {"deployment_mode": deployment_info["deployment_mode"]},
                document,
                upsert=True
            )
            
            return result.acknowledged
            
        except Exception as e:
            logger.error(f"❌ Error storing deployment info: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("🔌 MongoDB connection closed")