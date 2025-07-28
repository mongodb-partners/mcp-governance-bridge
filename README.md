# MCP Governance Bridge

A comprehensive governance and monitoring solution for Model Context Protocol (MCP) servers that provides centralized management, real-time monitoring, and security enforcement through a unified FastMCP-based architecture.

## 🏗️ Architecture Overview

```mermaid
graph TB
    subgraph "External Clients"
        A[MCP Clients]
        B[AI Assistants]
        C[Applications]
    end
    
    subgraph "MCP Governance Bridge"
        D[FastMCP Governance Server]
        E[Governance Engine]
        F[Usage Tracker]
        G[MongoDB Atlas Client]
        H[Config Loader]
        I[Streamlit Dashboard]
    end
    
    subgraph "Managed MCP Servers"
        J[Server 1<br/>stdio]
        K[Server 2<br/>HTTP]
        L[Server 3<br/>WebSocket]
        M[Server N<br/>...]
    end
    
    subgraph "Data Storage"
        N[(MongoDB Atlas)]
    end
    
    subgraph "Web Interface"
        O[Dashboard UI<br/>localhost:8501]
    end
    
    A --> D
    B --> D
    C --> D
    
    D --> E
    D --> F
    D --> G
    D --> H
    
    D --> J
    D --> K
    D --> L
    D --> M
    
    E --> G
    F --> G
    G --> N
    
    I --> G
    I --> O
    
    classDef client fill:#e1f5fe
    classDef governance fill:#f3e5f5
    classDef server fill:#e8f5e8
    classDef storage fill:#fff3e0
    classDef ui fill:#fce4ec
    
    class A,B,C client
    class D,E,F,G,H governance
    class J,K,L,M server
    class N storage
    class I,O ui
```

### Architecture Diagram Explanation

This diagram shows the high-level architecture of the MCP Governance Bridge:

- **External Clients**: Various MCP clients (AI assistants, applications) that need to interact with MCP servers
- **Governance Bridge**: The core system that acts as a proxy, providing governance, monitoring, and security
- **Managed MCP Servers**: The actual MCP servers being governed, supporting different transport protocols
- **Data Storage**: MongoDB Atlas for persistent storage of logs, metrics, and configuration
- **Web Interface**: Streamlit dashboard for monitoring and management

The bridge acts as a centralized governance layer that all clients must go through to access the underlying MCP servers.

## 🔄 Control Flow Diagram

```mermaid
flowchart TD
    subgraph "Tool Call Flow"
        A[Client Tool Request] --> B[Governance Middleware]
        B --> C{Governance Check}
        C -->|PASS| D[Execute Tool]
        C -->|FAIL| E[Deny Request]
        D --> F[Log Success]
        E --> G[Log Denial]
        F --> H[Return Result]
        G --> I[Return Error]
    end
    
    subgraph "Governance Policy Engine"
        J[Load Server Config] --> K[Time Restrictions]
        K --> L[Rate Limiting]
        L --> M[Security Patterns]
        M --> N[High Security Mode]
        N --> O[Policy Decision]
    end
    
    subgraph "Data Flow"
        P[Tool Invocation] --> Q[Store in MongoDB]
        Q --> R[Usage Analytics]
        R --> S[Dashboard Display]
        T[Governance Decision] --> U[Store Policy Log]
        U --> V[Compliance Reporting]
    end
    
    B --> J
    O --> C
    F --> P
    G --> T
    
    classDef request fill:#ffebee
    classDef process fill:#e8f5e8
    classDef storage fill:#fff3e0
    classDef decision fill:#f3e5f5
    
    class A,P,T request
    class B,D,J,K,L,M,N,R process
    class Q,U,S,V storage
    class C,O decision
```

### Control Flow Diagram Explanation

This diagram illustrates the request processing flow:

1. **Tool Call Flow**: Shows how client requests are processed through the governance middleware
2. **Governance Policy Engine**: Details the multi-stage policy evaluation process
3. **Data Flow**: Demonstrates how data flows from execution to storage to dashboard visualization

The governance engine evaluates requests through multiple layers of security checks before allowing or denying access.

## 📋 Sequence Diagram

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Middleware as Governance Middleware
    participant Engine as Governance Engine
    participant MongoDB as MongoDB Atlas
    participant Server as MCP Server
    participant Dashboard as Dashboard
    
    Note over Client,Dashboard: Tool Execution Flow
    
    Client->>Middleware: call_tool(name, args)
    
    Note over Middleware: Generate Session ID
    Middleware->>MongoDB: store_tool_log(invocation)
    
    Middleware->>Engine: check_governance(server, tool, args)
    
    Note over Engine: Policy Evaluation
    Engine->>Engine: check_time_restrictions()
    Engine->>Engine: check_rate_limit()
    Engine->>Engine: check_security_patterns()
    Engine->>Engine: check_high_security_mode()
    
    Engine->>MongoDB: store_governance_log(decision)
    
    alt Governance Check PASSES
        Engine-->>Middleware: {allowed: true}
        
        Middleware->>Server: execute_tool(name, args)
        Server-->>Middleware: tool_result
        
        Middleware->>MongoDB: store_tool_log(success)
        Middleware-->>Client: tool_result
        
    else Governance Check FAILS
        Engine-->>Middleware: {allowed: false, reason}
        
        Middleware->>MongoDB: store_tool_log(denied)
        Middleware-->>Client: GovernanceError(reason)
    end
    
    Note over Dashboard: Real-time Updates
    Dashboard->>MongoDB: get_usage_metrics()
    Dashboard->>MongoDB: get_governance_violations()
    Dashboard->>MongoDB: get_tool_logs()
    
    MongoDB-->>Dashboard: aggregated_data
    
    Note over Dashboard: Display Updates
    Dashboard->>Dashboard: update_charts()
    Dashboard->>Dashboard: refresh_metrics()
```

### Sequence Diagram Explanation

This sequence diagram shows the complete lifecycle of a tool execution request:

1. **Initial Request**: Client sends a tool call to the governance middleware
2. **Logging Start**: Middleware logs the invocation attempt to MongoDB
3. **Governance Check**: Engine evaluates the request against multiple policy layers:
   - Time restrictions (allowed hours)
   - Rate limiting (requests per minute)
   - Security patterns (dangerous operations)
   - High security mode (additional restrictions)
4. **Decision Storage**: The governance decision is logged for audit purposes
5. **Execution Path**: Based on the decision:
   - **Allowed**: Tool is executed on the target server, result is returned and logged
   - **Denied**: Request is blocked, error is returned and logged
6. **Dashboard Updates**: The dashboard continuously queries MongoDB for real-time metrics and updates

## 🔍 Data Flow Diagram

```mermaid
graph LR
    subgraph "Data Sources"
        A[Tool Invocations]
        B[Governance Decisions]
        C[Server Status]
        D[Configuration Changes]
    end
    
    subgraph "Data Processing"
        E[MongoDB Collections]
        F[Aggregation Pipeline]
        G[Analytics Engine]
    end
    
    subgraph "Data Consumers"
        H[Dashboard Charts]
        I[Compliance Reports]
        J[Alert System]
        K[Export Functions]
    end
    
    A --> E
    B --> E
    C --> E
    D --> E
    
    E --> F
    F --> G
    
    G --> H
    G --> I
    G --> J
    G --> K
    
    subgraph "MongoDB Collections Detail"
        E1[tool_logs]
        E2[governance_logs]
        E3[servers]
        E4[server_tools]
        E5[governance_configs]
    end
    
    E --> E1
    E --> E2
    E --> E3
    E --> E4
    E --> E5
    
    classDef source fill:#e3f2fd
    classDef process fill:#f3e5f5
    classDef consumer fill:#e8f5e8
    classDef collection fill:#fff3e0
    
    class A,B,C,D source
    class E,F,G process
    class H,I,J,K consumer
    class E1,E2,E3,E4,E5 collection
```

### Data Flow Diagram Explanation

This diagram illustrates how data flows through the system:

- **Data Sources**: Various events and state changes that generate data
- **Data Processing**: MongoDB storage and aggregation pipeline for analytics
- **Data Consumers**: Different ways the processed data is consumed and presented
- **MongoDB Collections**: Specific database collections that store different types of data

The system maintains a comprehensive audit trail while providing real-time analytics and reporting capabilities.

## 🚀 Features

### Core Governance Features
- **Multi-Mode Architecture**: Unified, multi-port, and hybrid deployment modes
- **Real-time Tool Monitoring**: Comprehensive logging and analytics
- **Security Enforcement**: Pattern blocking, rate limiting, time restrictions
- **Policy Management**: Configurable governance policies per server
- **Compliance Tracking**: Detailed audit logs and violation reports

### Monitoring & Analytics
- **Interactive Dashboard**: Real-time Streamlit-based web interface
- **Usage Analytics**: Tool performance metrics and usage patterns
- **Server Health**: Status monitoring and uptime tracking
- **Violation Alerts**: Governance policy violation detection

### Data Management
- **MongoDB Atlas Integration**: Scalable cloud database storage
- **Structured Logging**: Comprehensive tool execution logs
- **Data Export**: JSON export functionality for compliance
- **Real-time Metrics**: Live dashboard updates

## 📋 Prerequisites

- **Python 3.11+**
- **MongoDB Atlas** account and connection string
- **UV package manager** (recommended) or pip
- **Git** for cloning the repository

## 🛠️ Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-org/mcp-governance-bridge.git
cd mcp-governance-bridge
```

2. **Install dependencies**
```bash
uv sync
# or with pip
pip install -r requirements.txt
```

3. **Configure MongoDB**
```bash
# Set environment variable
export MONGODB_URI="mongodb+srv://username:password@cluster.mongodb.net/mcp_governance"
# or create .env file
echo "MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/mcp_governance" > .env
```

4. **Create configuration file**
```bash
cp config.example.json mcp_governance_config.json
# Edit with your MCP server configurations
```

## ⚙️ Configuration

### Basic Configuration Structure

```json
{
  "governance": {
    "deployment_mode": "unified",
    "base_port": 8173,
    "enable_tracking": true,
    "enable_dashboard": true,
    "mongodb_uri": "mongodb+srv://...",
    "auth_disabled": true,
    "transformation_strategy": "fastmcp_native"
  },
  "mcpServers": {
    "weather-server": {
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "weather_server"],
      "env": {
        "WEATHER_API_KEY": "your-api-key"
      },
      "governance": {
        "mode": "unified",
        "rate_limit": 100,
        "high_security": false,
        "allowed_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
        "governance_prefix": "governed_",
        "detailed_tracking": true
      }
    }
  }
}
```

### Deployment Modes

- **Unified Mode**: All servers behind single governance proxy
- **Multi-Port Mode**: Each server on separate governed port
- **Hybrid Mode**: Mix of unified and separate deployments

### Governance Options

- **Rate Limiting**: Requests per minute per server
- **Time Restrictions**: Allowed hours of operation
- **Security Patterns**: Block dangerous operations
- **High Security Mode**: Enhanced security checks
- **Detailed Tracking**: Comprehensive usage logging

## 🏃 Running the Application

### Quick Start
```bash
# Using the provided launcher
chmod +x run.sh
./run.sh
```

### Manual Start
```bash
# Start main governance server
uv run app/main.py

# Start dashboard (in another terminal)
uv run streamlit run dashboard/streamlit_dashboard.py --server.port=8501
```

### Access Points
- **Dashboard**: http://localhost:8501
- **Main Server**: http://localhost:8173 (unified mode)
- **API Documentation**: http://localhost:8173/docs

## 📊 Dashboard Features

### Overview Tab
- System status and health metrics
- Tool usage statistics
- Success rate analytics
- Server activity monitoring

### Servers Tab
- Server configuration management
- Health status monitoring
- Individual server metrics
- Tool inventory per server

### Tool Analytics Tab
- Performance metrics
- Usage patterns
- Success/failure rates
- Duration analytics

### Governance Tab
- Policy compliance monitoring
- Violation tracking
- Decision audit logs
- Policy effectiveness analysis

### Tool Logs Tab
- Detailed execution logs
- Input/output tracking
- Error analysis
- Session monitoring

### System Tab
- Database connection status
- Collection statistics
- Configuration export
- System maintenance

## 🔐 Security Features

### Policy Engine
```python
# Example governance policy
{
  "max_requests_per_minute": 100,
  "allowed_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
  "blocked_patterns": [
    r"(password|secret|token|key)\s*[:=]\s*\w+",
    r"(rm|del|delete)\s+-rf",
    r"drop\s+table",
    r"eval\s*\(",
    r"exec\s*\("
  ],
  "high_security_mode": false
}
```

### Monitoring & Alerting
- Real-time violation detection
- Policy breach notifications
- Usage anomaly detection
- Compliance reporting

## 🗃️ Data Models

### Tool Execution Log
```json
{
  "session_id": "uuid",
  "server_name": "weather-server",
  "tool_name": "get_weather",
  "event_type": "tool_completion",
  "start_time": "2024-01-01T10:00:00Z",
  "end_time": "2024-01-01T10:00:01Z",
  "duration_ms": 1000,
  "status": "success",
  "inputs": {...},
  "outputs": {...},
  "error_message": null
}
```

### Governance Decision Log
```json
{
  "server_name": "weather-server",
  "tool_name": "get_weather",
  "decision": "allowed",
  "policy_applied": {...},
  "timestamp": "2024-01-01T10:00:00Z",
  "governance_version": "1.0"
}
```

## 🔧 API Endpoints

### Governance API
```bash
# Get tool logs
GET /governance/tool-logs?server_name=weather-server&hours=24

# Get server status
GET /governance/servers

# Get governance metrics
GET /governance/metrics?hours=24

# Get violations
GET /governance/violations?hours=24
```

### Health Check
```bash
# System status
GET /

# Dashboard redirect
GET /dashboard
```

## 📈 Metrics & Analytics

### Usage Metrics
- Tool execution counts
- Success/failure rates
- Average execution time
- Server utilization
- User session tracking

### Governance Metrics
- Policy compliance rates
- Violation frequency
- Security pattern matches
- Rate limit breaches
- Time restriction violations

### Performance Metrics
- Response times
- Throughput analysis
- Error rates
- Resource utilization
- Database performance

## 🧪 Testing

```bash
# Run unit tests
uv run pytest tests/

# Test with coverage
uv run pytest tests/ --cov=app --cov=core --cov=database

# Integration tests
uv run pytest tests/integration/

# Load testing
uv run pytest tests/load/
```

## 🐛 Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
```bash
# Check connection string
echo $MONGODB_URI
# Verify network access
ping cluster.mongodb.net
```

2. **Server Not Starting**
```bash
# Check logs
tail -f logs/mcp_governance.log
# Verify port availability
lsof -i :8173
```

3. **Dashboard Loading Issues**
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/
# Restart dashboard
uv run streamlit run dashboard/streamlit_dashboard.py --server.port=8501
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uv run app/main.py
```

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Development Setup
```bash
# Install development dependencies
uv sync --dev

# Run code formatting
uv run black .

# Run linting
uv run flake8 .

# Run type checking
uv run mypy .
```

## 📄 License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Dashboard powered by [Streamlit](https://streamlit.io/)
- Data storage with [MongoDB Atlas](https://www.mongodb.com/atlas)
- Visualization with [Plotly](https://plotly.com/)

## 📞 Support

For support, please:
1. Check the troubleshooting guide
2. Search existing issues
3. Create a new issue with detailed information
4. Contact the development team

---

**MCP Governance Bridge** - Secure, scalable, and comprehensive MCP server management solution.