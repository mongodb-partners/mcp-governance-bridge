# app/governance_server_manager.py
import asyncio
import uuid
from datetime import datetime, timezone
from fastmcp import FastMCP, Client
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from typing import Dict, List, Any, Optional
import mcp.types as mt
from database.atlas_client import MongoDBAtlasClient
from core.governance_engine import GovernanceEngine
from utils.config_loader import ConfigLoader
from utils.logger import logger

class GovernanceLoggingMiddleware(Middleware):
    """Middleware that handles governance and logging for all tool calls."""
    
    def __init__(self, governance_manager, server_name: str):
        self.governance_manager = governance_manager
        self.server_name = server_name
    
    async def on_call_tool(
        self, 
        context: MiddlewareContext[mt.CallToolRequestParams], 
        call_next: CallNext[mt.CallToolRequestParams, mt.CallToolResult]
    ) -> mt.CallToolResult:
        """Handle governance and logging for tool calls."""
        
        session_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        tool_name = context.message.name
        arguments = context.message.arguments or {}
        
        # Log invocation
        await self.governance_manager._log_tool_invocation(
            session_id, self.server_name, tool_name, arguments, start_time, True
        )
        
        try:
            # Governance check
            governance_config= await self.governance_manager._get_governance_config(self.server_name) or {}
            print(f"Checking governance for {self.server_name}.{tool_name} with config: {governance_config}")
            governance_result = await self.governance_manager.governance_engine.check_governance(
                self.server_name, tool_name, arguments, governance_config
            )
            
            if not governance_result['allowed']:
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                await self.governance_manager._log_tool_completion(
                    session_id, self.server_name, tool_name, arguments, None,
                    "denied", governance_result.get('reason'), duration_ms, datetime.now(timezone.utc)
                )
                raise Exception(f"Governance denied: {governance_result['reason']}")
            
            # Execute the actual tool
            logger.info(f"🔧 Executing tool: {self.server_name}.{tool_name}")
            result = await call_next(context)
            
            # Log success
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            await self.governance_manager._log_tool_completion(
                session_id, self.server_name, tool_name, arguments, result,
                "success", None, duration_ms, datetime.now(timezone.utc)
            )
            
            logger.info(f"✅ Tool execution completed: {self.server_name}.{tool_name}")
            return result
            
        except Exception as e:
            # Log error
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            await self.governance_manager._log_tool_completion(
                session_id, self.server_name, tool_name, arguments, None,
                "error", str(e), duration_ms, datetime.now(timezone.utc)
            )
            logger.error(f"❌ Tool execution failed: {self.server_name}.{tool_name}: {e}")
            raise


class MCPGovernanceManager:
    """Governance manager using FastMCP middleware."""
    
    def __init__(self, config_path: str = "mcp_governance_config.json"):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        self.mongodb_client = MongoDBAtlasClient()
        self.governance_engine = GovernanceEngine(self.mongodb_client)
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.unified_server: Optional[FastMCP] = None
        self.server_tasks: List[asyncio.Task] = []
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        logger.info("✅ Governance Manager initialized")

    async def _mount_server_with_governance(self, governance_server: FastMCP,
                                          server_name: str, server_config: dict) -> bool:
        """Mount server using FastMCP proxy with middleware"""
        try:
            logger.info(f"🔧 Mounting {server_name} with governance middleware...")
            
            # Create client
            client = await self._create_mcp_client(server_name, server_config)
            
            # Test connection
            async with asyncio.timeout(10):
                async with client:
                    tools = await client.list_tools()
                    logger.info(f"✅ {server_name} connected with {len(tools)} tools")
                    await self._store_server_tools(server_name, tools)

            # Create proxy server
            proxy = FastMCP.as_proxy(client)
            
            # Add governance middleware to the proxy
            governance_middleware = GovernanceLoggingMiddleware(self, server_name)
            proxy.add_middleware(governance_middleware)
            
            # Mount with prefix - FastMCP handles the prefixing automatically
            mount_prefix = server_config.get('governance', {}).get('governance_prefix', 'governed_')
            governance_server.mount(proxy, prefix=mount_prefix)
            
            logger.info(f"✅ Mounted {server_name} with middleware (prefix: {mount_prefix}_)")
            
            # Store server info
            await self._store_server_info(server_name, server_config)
            await self._store_governance_config(server_name, server_config)
            
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"❌ {server_name} connection timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to mount {server_name}: {e}")
            return False

    # Logging methods
    async def _log_tool_invocation(self, session_id: str, server_name: str, 
                                 tool_name: str, inputs: Dict[str, Any], 
                                 start_time: datetime, detailed_tracking: bool):
        """Log tool invocation to MongoDB."""
        try:
            log_entry = {
                "session_id": session_id,
                "server_name": server_name,
                "tool_name": tool_name,
                "event_type": "tool_invocation",
                "start_time": start_time,
                "status": "invocation request received",
                "inputs": inputs,
                "input_size": len(str(inputs)),
                "timestamp": start_time,
                "environment": {
                    "deployment_mode": self.config.get('governance', {}).get('deployment_mode', 'unknown'),
                    "governance_enabled": True,
                    "detailed_tracking": detailed_tracking
                }
            }
            
            await self.mongodb_client.store_tool_log(log_entry)
            logger.debug(f"📝 Logged tool invocation: {server_name}.{tool_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log tool invocation: {e}")

    async def _log_tool_completion(self, session_id: str, server_name: str, 
                                tool_name: str, inputs: Dict[str, Any], 
                                outputs: Any, status: str, error_message: Optional[str],
                                duration_ms: float, end_time: datetime):
        """Log tool completion to MongoDB with proper serialization."""
        try:
            log_entry = {
                "session_id": session_id,
                "server_name": server_name,
                "tool_name": tool_name,
                "event_type": "tool_completion",
                "end_time": end_time,
                "status": status,
                "duration_ms": duration_ms,
                "error_message": error_message,
                "timestamp": end_time
            }
            
            # Add outputs if successful 
            if status == "success" and outputs is not None:
                try:
                    serialized_outputs = await self._serialize_tool_outputs(outputs)
                    log_entry["outputs"] = serialized_outputs
                    log_entry["output_size"] = len(str(serialized_outputs))
                except Exception as serialize_error:
                    logger.warning(f"Failed to serialize outputs for {tool_name}: {serialize_error}")
                    log_entry["outputs"] = {"error": "Failed to serialize", "type": str(type(outputs))}
                    log_entry["output_size"] = 0
            
            await self.mongodb_client.store_tool_log(log_entry)
            logger.debug(f"📝 Logged tool completion: {server_name}.{tool_name} ({status})")
            
        except Exception as e:
            logger.error(f"❌ Failed to log tool completion: {e}")

    async def _serialize_tool_outputs(self, outputs: Any) -> Dict[str, Any]:
        """Serialize tool outputs to MongoDB-compatible format."""
        try:
            # Import MCP types for checking
            from mcp.types import TextContent, ImageContent, EmbeddedResource
            from mcp.types import CallToolResult
            
            serialized = {}
            
            # Handle CallToolResult objects
            if hasattr(outputs, 'content') and hasattr(outputs, 'isError'):
                # This is a CallToolResult
                serialized = {
                    "type": "CallToolResult",
                    "isError": getattr(outputs, 'isError', False),
                    "content": [],
                    "structured_content": getattr(outputs, 'structured_content', None)
                }
                
                # Serialize content blocks
                if outputs.content:
                    for content_item in outputs.content:
                        if isinstance(content_item, TextContent):
                            serialized["content"].append({
                                "type": "text",
                                "text": content_item.text,
                                "annotations": content_item.annotations,
                                "meta": content_item.meta
                            })
                        elif isinstance(content_item, ImageContent):
                            serialized["content"].append({
                                "type": "image",
                                "data": str(content_item.data)[:1000] + "..." if len(str(content_item.data)) > 1000 else str(content_item.data),
                                "mimeType": content_item.mimeType,
                                "annotations": content_item.annotations,
                                "meta": content_item.meta
                            })
                        elif isinstance(content_item, EmbeddedResource):
                            serialized["content"].append({
                                "type": "resource",
                                "resource": {
                                    "uri": str(content_item.resource.uri),
                                    "text": content_item.resource.text[:1000] + "..." if content_item.resource.text and len(content_item.resource.text) > 1000 else content_item.resource.text,
                                    "mimeType": content_item.resource.mimeType
                                },
                                "annotations": content_item.annotations,
                                "meta": content_item.meta
                            })
                        else:
                            # Unknown content type, convert to string
                            serialized["content"].append({
                                "type": "unknown",
                                "data": str(content_item)[:1000] + "..." if len(str(content_item)) > 1000 else str(content_item),
                                "original_type": str(type(content_item))
                            })
                
                # Handle structured_content if present
                if hasattr(outputs, 'structured_content') and outputs.structured_content:
                    try:
                        # Ensure structured_content is JSON serializable
                        serialized["structured_content"] = self._make_json_serializable(outputs.structured_content)
                    except Exception as sc_error:
                        logger.warning(f"Failed to serialize structured_content: {sc_error}")
                        serialized["structured_content"] = {"error": "Failed to serialize structured content"}
            
            # Handle other object types
            elif hasattr(outputs, '__dict__'):
                # Generic object with attributes
                serialized = {
                    "type": "object",
                    "class": str(type(outputs)),
                    "attributes": self._make_json_serializable(outputs.__dict__)
                }
            
            # Handle simple types
            elif isinstance(outputs, (str, int, float, bool, type(None))):
                serialized = {
                    "type": "primitive",
                    "value": outputs,
                    "python_type": str(type(outputs))
                }
            
            # Handle lists and dicts
            elif isinstance(outputs, (list, dict)):
                serialized = {
                    "type": "collection",
                    "data": self._make_json_serializable(outputs),
                    "python_type": str(type(outputs))
                }
            
            # Fallback - convert to string
            else:
                output_str = str(outputs)
                serialized = {
                    "type": "string_representation",
                    "data": output_str[:1000] + "..." if len(output_str) > 1000 else output_str,
                    "original_type": str(type(outputs)),
                    "truncated": len(output_str) > 1000
                }
            
            return serialized
            
        except Exception as e:
            logger.error(f"Error in _serialize_tool_outputs: {e}")
            return {
                "type": "serialization_error",
                "error": str(e),
                "fallback_string": str(outputs)[:500] if outputs else None
            }

    def _make_json_serializable(self, obj: Any, max_depth: int = 5) -> Any:
        """Recursively make an object JSON serializable."""
        if max_depth <= 0:
            return {"error": "Max depth reached", "type": str(type(obj))}
        
        try:
            # Handle None, bool, int, float, str
            if obj is None or isinstance(obj, (bool, int, float, str)):
                return obj
            
            # Handle lists
            elif isinstance(obj, list):
                return [self._make_json_serializable(item, max_depth - 1) for item in obj[:100]]  # Limit to 100 items
            
            # Handle dicts
            elif isinstance(obj, dict):
                result = {}
                for key, value in list(obj.items())[:50]:  # Limit to 50 keys
                    try:
                        json_key = str(key) if not isinstance(key, str) else key
                        result[json_key] = self._make_json_serializable(value, max_depth - 1)
                    except Exception:
                        result[json_key] = {"error": "Failed to serialize", "type": str(type(value))}
                return result
            
            # Handle objects with __dict__
            elif hasattr(obj, '__dict__'):
                return {
                    "type": str(type(obj)),
                    "attributes": self._make_json_serializable(obj.__dict__, max_depth - 1)
                }
            
            # Handle other iterables (tuples, sets, etc.)
            elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                try:
                    return [self._make_json_serializable(item, max_depth - 1) for item in list(obj)[:100]]
                except Exception:
                    pass
            
            # Fallback to string representation
            obj_str = str(obj)
            return {
                "string_representation": obj_str[:500] + "..." if len(obj_str) > 500 else obj_str,
                "type": str(type(obj)),
                "truncated": len(obj_str) > 500
            }
            
        except Exception as e:
            return {
                "serialization_error": str(e),
                "type": str(type(obj)),
                "fallback": str(obj)[:200] if obj else None
        }

    async def setup_all_servers(self):
        """Setup servers based on configuration mode."""
        deployment_mode = self.config['governance']['deployment_mode']
        logger.info(f"🏗️ Setting up servers in {deployment_mode} mode")
        
        # Store deployment info
        deployment_info = {
            "deployment_mode": deployment_mode,
            "base_port": self.config['governance']['base_port'],
            "total_servers": len(self.config['mcpServers']),
            "transformation_strategy": "middleware_based",
            "setup_time": datetime.now(timezone.utc).isoformat(),
            "status": "initializing"
        }
        await self.mongodb_client.store_deployment_info(deployment_info)
        
        if deployment_mode == "unified":
            await self._setup_unified_mode()
        elif deployment_mode == "multi-port":
            await self._setup_multi_port_mode()
        elif deployment_mode == "hybrid":
            await self._setup_hybrid_mode()
        else:
            raise ValueError(f"Unknown deployment mode: {deployment_mode}")
        
        # Update deployment status
        deployment_info["status"] = "ready"
        await self.mongodb_client.store_deployment_info(deployment_info)
        
        logger.info(f"🎉 All servers setup complete in {deployment_mode} mode")

    async def _setup_unified_mode(self):
        """Setup all MCPs behind one governance proxy."""
        base_port = self.config['governance']['base_port']
        
        # Create unified governance server
        self.unified_server = FastMCP("mcp-governance-bridge-unified")
        
        # Add routes and mount servers
        await self._setup_server_routes_and_mounts(self.unified_server)
        
        # Store server info
        self.servers['unified'] = {
            'server': self.unified_server,
            'port': base_port,
            'config': self.config,
            'status': 'ready'
        }
        
        logger.info(f"🌐 Unified server ready on port {base_port}")

    async def _setup_multi_port_mode(self):
        """Setup each MCP on its own governed port."""
        for server_name, server_config in self.config['mcpServers'].items():
            port = server_config.get('governance', {}).get('port', 8174)
            
            # Create individual governance server
            server = FastMCP(f"governance-{server_name.lower()}")
            
            # Setup this specific server
            await self._setup_individual_server(server, server_name, server_config)
            
            self.servers[server_name] = {
                'server': server,
                'port': port,
                'config': server_config,
                'status': 'ready'
            }
            
            logger.info(f"🔧 {server_name} server ready on port {port}")

    async def _setup_hybrid_mode(self):
        """Setup mix of unified and separate servers."""
        # Setup unified server for 'unified' mode servers
        unified_servers = {
            name: config for name, config in self.config['mcpServers'].items()
            if config.get('governance', {}).get('mode', 'unified') == 'unified'
        }
        
        if unified_servers:
            base_port = self.config['governance']['base_port']
            self.unified_server = FastMCP("mcp-governance-bridge-unified")
            
            await self._setup_server_routes_and_mounts(self.unified_server, unified_servers)
            
            self.servers['unified'] = {
                'server': self.unified_server,
                'port': base_port,
                'config': self.config,
                'status': 'ready'
            }
            
            logger.info(f"🌐 Unified server ready on port {base_port}")
        
        # Setup separate servers
        separate_servers = {
            name: config for name, config in self.config['mcpServers'].items()
            if config.get('governance', {}).get('mode') == 'separate_port'
        }
        
        for server_name, server_config in separate_servers.items():
            port = server_config.get('governance', {}).get('port', 8174)
            server = FastMCP(f"governance-{server_name.lower()}")
            
            await self._setup_individual_server(server, server_name, server_config)
            
            self.servers[server_name] = {
                'server': server,
                'port': port,
                'config': server_config,
                'status': 'ready'
            }
            
            logger.info(f"🔧 {server_name} server ready on port {port}")

    async def _setup_server_routes_and_mounts(self, server: FastMCP, server_configs: Dict[str, Any] = None):
        """Setup routes and mount MCP servers with governance."""
        # Add dashboard and API routes
        self._add_dashboard_routes(server)
        self._add_governance_api_routes(server)
        
        # Mount servers
        server_configs = server_configs or self.config['mcpServers']
        mounted_count = 0
        
        for server_name, server_config in server_configs.items():
            success = await self._mount_server_with_governance(server, server_name, server_config)
            if success:
                mounted_count += 1
        
        logger.info(f"✅ Mounted {mounted_count}/{len(server_configs)} servers")

    async def _setup_individual_server(self, server: FastMCP, server_name: str, server_config: Dict[str, Any]):
        """Setup individual server with governance."""
        self._add_dashboard_routes(server)
        self._add_governance_api_routes(server)
        
        await self._mount_server_with_governance(server, server_name, server_config)

    async def _create_mcp_client(self, server_name: str, server_config: dict) -> Client:
        """Create MCP client based on transport type."""
        transport = server_config.get('transport', 'stdio')
        
        if transport == 'stdio':
            command = server_config.get('command')
            args = server_config.get('args', [])
            env = server_config.get('env', {})
            
            if not command:
                raise ValueError(f"Missing command for stdio server: {server_name}")
            
            # Merge environment variables
            import os
            full_env = {**os.environ, **env}
            
            # Create client configuration
            client_config = {
                "mcpServers": {
                    server_name.lower().replace('-', '_'): {
                        "transport": "stdio",
                        "command": command,
                        "args": args,
                        "env": full_env
                    }
                }
            }
            
            return Client(client_config)
        
        elif transport in ['streamable-http', 'http']:
            url = server_config.get('url')
            if not url:
                raise ValueError(f"Missing URL for HTTP server: {server_name}")
            
            return Client(url)
        
        else:
            raise ValueError(f"Unsupported transport: {transport}")

    # Add your dashboard and API routes methods here (keep them the same)
    def _add_dashboard_routes(self, server: FastMCP):
        """Add dashboard routes to server."""
        @server.custom_route("/dashboard", methods=["GET"])
        async def dashboard(request):
            """Dashboard redirect to Streamlit."""
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="http://localhost:8501")
        
        @server.custom_route("/", methods=["GET"])
        async def root(request):
            """Root endpoint with server info."""
            from starlette.responses import JSONResponse
            
            server_info = {
                "service": "MCP Governance Bridge",
                "version": "1.0.0",
                "mode": self.config['governance']['deployment_mode'],
                "transformation_strategy": "middleware_based",
                "dashboard": "http://localhost:8501",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "running" if self.is_running else "stopped"
            }
            
            return JSONResponse(server_info)

    def _add_governance_api_routes(self, server: FastMCP):
        """Add governance API routes to server."""
        @server.custom_route("/governance/tool-logs", methods=["GET"])
        async def get_tool_logs(request):
            """Get tool execution logs."""
            from starlette.responses import JSONResponse
            
            try:
                # Get query parameters
                server_name = request.query_params.get('server_name')
                tool_name = request.query_params.get('tool_name')
                session_id = request.query_params.get('session_id')
                hours = int(request.query_params.get('hours', 24))
                limit = int(request.query_params.get('limit', 100))
                
                logs_data = await self.mongodb_client.get_tool_logs(
                    server_name=server_name,
                    tool_name=tool_name,
                    session_id=session_id,
                    hours=hours,
                    limit=limit
                )
                return JSONResponse({"status": "success", "data": logs_data})
            except Exception as e:
                return JSONResponse({"status": "error", "error": str(e)})


    async def _store_server_tools(self, server_name: str, tools: List[Any]):
        """Store server tools information in MongoDB."""
        tools_info = []
        for tool in tools:
            tool_info = {
                "server_name": server_name,
                "tool_name": tool.name,
                "description": getattr(tool, 'description', ''),
                "parameters": getattr(tool, 'inputSchema', {}),
                "discovered_at": datetime.now(timezone.utc).isoformat()
            }
            tools_info.append(tool_info)
        
        await self.mongodb_client.store_server_tools(tools_info)

    async def _store_server_info(self, server_name: str, server_config: dict):
        """Store server information in MongoDB."""
        import hashlib
        server_info = {
            "server_name": server_name,
            "transport": server_config.get('transport'),
            "governance_mode": server_config.get('governance', {}).get('mode', 'unified'),
            "rate_limit": server_config.get('governance', {}).get('rate_limit'),
            "port": server_config.get('governance', {}).get('port'),
            "is_active": True,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "config_hash": hashlib.sha256(str(server_config).encode()).hexdigest()
        }
        
        await self.mongodb_client.store_server_info(server_info)

    async def _store_governance_config(self, server_name: str, server_config: dict):
        """Store governance configuration."""
        governance_config = server_config.get('governance', {})
        
        governance_info = {
            "server_name": server_name,
            "rate_limit": governance_config.get('rate_limit', 100),
            "high_security": governance_config.get('high_security', False),
            "allowed_hours": governance_config.get('allowed_hours', list(range(24))),
            "track_api_usage": governance_config.get('track_api_usage', True),
            "security_level": governance_config.get('security_level', 'medium'),
            "mode": governance_config.get('mode', 'unified'),
            "hide_original_tools": governance_config.get('hide_original_tools', True),
            "governance_prefix": governance_config.get('governance_prefix', 'governed_'),
            "detailed_tracking": governance_config.get('detailed_tracking', True),
            "enable_tool_logging": governance_config.get('enable_tool_logging', True),
            "enabled_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.mongodb_client.store_governance_config(governance_info)
        logger.info(f"📋 Stored governance config for {server_name}")

    async def _get_governance_config(self, server_name: str) -> Optional[dict]:
        """Get governance configuration for a server."""
        try:
            governance_info = await self.mongodb_client.get_governance_config(server_name)
            
            if not governance_info:
                logger.warning(f"📋 No governance config found for {server_name}")
                return None
            
            # Extract the governance config with defaults
            governance_config = {
                'rate_limit': governance_info.get('rate_limit', 100),
                'high_security': governance_info.get('high_security', False),
                'allowed_hours': governance_info.get('allowed_hours', list(range(24))),
                'track_api_usage': governance_info.get('track_api_usage', True),
                'security_level': governance_info.get('security_level', 'medium'),
                'mode': governance_info.get('mode', 'unified'),
                'hide_original_tools': governance_info.get('hide_original_tools', True),
                'governance_prefix': governance_info.get('governance_prefix', 'governed_'),
                'detailed_tracking': governance_info.get('detailed_tracking', True),
                'enable_tool_logging': governance_info.get('enable_tool_logging', True)
            }
            
            logger.info(f"📋 Retrieved governance config for {server_name}")
            return governance_config
            
        except Exception as e:
            logger.error(f"❌ Error retrieving governance config for {server_name}: {e}")
            return None


    async def run_servers(self):
        """Run all configured servers."""
        self.is_running = True
        logger.info("🚀 Starting MCP Governance Bridge servers...")
        
        try:
            tasks = []
            
            # Run unified server if configured
            if self.unified_server and 'unified' in self.servers:
                port = self.servers['unified']['port']
                task = asyncio.create_task(
                    self._run_single_server(self.unified_server, "0.0.0.0", port, "Unified Server")
                )
                tasks.append(task)
            
            # Run individual servers
            for server_name, server_info in self.servers.items():
                if server_name != 'unified':
                    server = server_info['server']
                    port = server_info['port']
                    task = asyncio.create_task(
                        self._run_single_server(server, "0.0.0.0", port, server_name)
                    )
                    tasks.append(task)
            
            self.server_tasks = tasks
            
            if not tasks:
                logger.warning("❌ No servers to run!")
                return
            
            logger.info(f"✅ Started {len(tasks)} server(s)")
            
            await asyncio.wait([
                asyncio.create_task(self.shutdown_event.wait()),
                *tasks
            ], return_when=asyncio.FIRST_COMPLETED)
                
        except Exception as e:
            logger.error(f"❌ Failed to run servers: {e}")
        finally:
            self.is_running = False
            logger.info("✅ All servers stopped")

    async def _run_single_server(self, server: FastMCP, host: str, port: int, name: str):
        """Run a single FastMCP server."""
        try:
            logger.info(f"🚀 Starting {name} on {host}:{port}")
            
            await server.run_async(
                transport="streamable-http",
                host=host,
                port=port,
                show_banner=True
            )
            
        except Exception as e:
            logger.error(f"❌ {name} server error: {e}")
            raise

    async def stop_servers(self):
        """Stop all running servers."""
        logger.info("🛑 Stopping servers...")
        self.is_running = False
        self.shutdown_event.set()
        await asyncio.sleep(2)