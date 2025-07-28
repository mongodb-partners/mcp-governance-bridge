# MCP Governance Bridge

```mermaid
graph TB
    subgraph "Business Value"
        BV1[Multi-Server Governance]
        BV2[Real-time Monitoring]
        BV3[Security & Compliance]
        BV4[Operational Insights]
    end

    subgraph "Architecture"
        A[MCP Governance Bridge<br/>Python FastMCP Framework]
        
        subgraph "Core Components"
            B[Governance Engine<br/>Policy Enforcement]
            C[Usage Tracker<br/>Session Management] 
            D[Server Manager<br/>Multi-Mode Deployment]
        end
        
        subgraph "Data & Monitoring"
            E[MongoDB Atlas<br/>Analytics & Logs]
            F[Streamlit Dashboard<br/>Real-time Insights]
        end
    end

    subgraph "External Systems"
        G[MCP Servers<br/>MongoDB, AWS, Tavily, etc.]
        H[Client Applications<br/>Claude, VS Code, etc.]
    end

    subgraph "Deployment Modes"
        I1[Unified Mode<br/>Single Endpoint]
        I2[Multi-Port Mode<br/>Isolated Services]
        I3[Hybrid Mode<br/>Mixed Deployment]
    end

    %% Business connections
    BV1 --> B
    BV2 --> F
    BV3 --> B
    BV4 --> E

    %% Technical flow
    A --> B
    A --> C
    A --> D
    B --> E
    C --> E
    D --> F
    F --> E
    
    G --> A
    A --> H
    
    D --> I1
    D --> I2
    D --> I3

    %% Styling
    classDef business fill:#e8f5e8,stroke:#4caf50,stroke-width:2px
    classDef core fill:#e3f2fd,stroke:#2196f3,stroke-width:2px
    classDef data fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    classDef external fill:#fce4ec,stroke:#e91e63,stroke-width:2px
    classDef deployment fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px

    class BV1,BV2,BV3,BV4 business
    class A,B,C,D core
    class E,F data
    class G,H external
    class I1,I2,I3 deployment
```

## 🗂️ **Project Structure**

```
mcp-governance-bridge/
├── app/
│   ├── __init__.py
│   ├── governance_server_manager.py
│   └── main.py
├── core/
│   ├── __init__.py
│   ├── usage_tracker.py
│   └── governance_engine.py
├── database/
│   ├── __init__.py
│   └── atlas_client.py
├── dashboard/
│   ├── __init__.py
│   ├── streamlit_dashboard.py
│   └── dashboard_utils.py
├── utils/
│   ├── __init__.py
│   └── config_loader.py
│   └── logger.py
├── requirements.txt
└── pyproject.toml
```

## 🚀 **Usage Instructions**

### **1. Setup**
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export MONGODB_URI="mongodb+srv://your-atlas-uri"
export MONGODB_DATABASE="mcp_governance"
```

### **2. Run the Application**
```bash
# Use run.sh
./run.sh
#============
# Or
# Start the governance bridge
python app/main.py

# Or use the CLI
mcp-governance
```

### **3. Access Dashboard**
```bash
# Dashboard will be available at:
http://localhost:8501
```

### **4. API Endpoints**
```bash
# Unified mode
http://localhost:8173/mcp/
http://localhost:8173/dashboard
http://localhost:8173/governance/metrics

# Multi-port mode
http://localhost:8174/mcp/  # Individual servers
http://localhost:8175/mcp/
http://localhost:8176/mcp/
```

This implementation provides:

✅ **Multi-Mode Deployment** (Unified, Multi-Port, Hybrid)  
✅ **Streamlit Dashboard** with real-time monitoring  
✅ **MongoDB Atlas Integration** for comprehensive data storage  
✅ **Usage Tracking** with detailed analytics  
✅ **Governance Engine** with policy enforcement  
✅ **Enterprise-Ready** architecture with proper error handling  
✅ **Configurable** through JSON configuration  
✅ **Extensible** design for adding new features  

The system automatically tracks all MCP tool usage, enforces governance policies, and provides comprehensive monitoring through the Streamlit dashboard!

