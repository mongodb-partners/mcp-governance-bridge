# dashboard/streamlit_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List
from database.atlas_client import MongoDBAtlasClient
from dashboard.dashboard_utils import DashboardUtils

# Page configuration
st.set_page_config(
    page_title="MCP Governance Bridge",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        margin: 0.5rem 0;
        text-align: center;
    }
    .metric-card h3 {
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .metric-card h2 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: bold;
    }
    .success-metric {
        background: linear-gradient(90deg, #56ab2f 0%, #a8e6cf 100%);
    }
    .error-metric {
        background: linear-gradient(90deg, #ff416c 0%, #ff4b2b 100%);
    }
    .warning-metric {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .tool-log-success {
        background-color: #d4edda;
        padding: 10px;
        border-left: 4px solid #28a745;
        margin: 5px 0;
        border-radius: 4px;
    }
    .tool-log-error {
        background-color: #f8d7da;
        padding: 10px;
        border-left: 4px solid #dc3545;
        margin: 5px 0;
        border-radius: 4px;
    }
    .tool-log-denied {
        background-color: #fff3cd;
        padding: 10px;
        border-left: 4px solid #ffc107;
        margin: 5px 0;
        border-radius: 4px;
    }
    .status-row {
        padding: 8px;
        margin: 4px 0;
        border-radius: 4px;
        border-left: 4px solid #007bff;
    }
</style>
""", unsafe_allow_html=True)

class MCPGovernanceDashboard:
    """Main dashboard class for MCP Governance Bridge."""
    
    def __init__(self):
        self.mongodb_client = MongoDBAtlasClient()
        self.utils = DashboardUtils()
        
        # Initialize session state
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = True
        if 'refresh_interval' not in st.session_state:
            st.session_state.refresh_interval = 30
        if 'chart_counter' not in st.session_state:
            st.session_state.chart_counter = 0
    
    def get_unique_key(self, prefix: str = "element") -> str:
        """Generate unique key for Streamlit elements."""
        st.session_state.chart_counter += 1
        session_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{st.session_state.chart_counter}_{session_id}"
    
    def run(self):
        """Run the dashboard."""
        self.render_header()
        self.render_sidebar()
        self.render_main_content()
        self.handle_auto_refresh()
    
    def render_header(self):
        """Render dashboard header."""
        st.title("🏛️ MCP Governance Bridge")
        st.markdown("**Multi-Mode Server Architecture Dashboard**")
        
        # Status indicator
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status_html = self.utils.create_metric_card(
                "🌐 System Status", 
                "Active", 
                "✅ Running",
                "success"
            )
            st.markdown(status_html, unsafe_allow_html=True)
        
        with col2:
            # Get server count
            try:
                servers = asyncio.run(self.mongodb_client.get_server_list())
                server_count = len(servers)
                active_servers = len([s for s in servers if s.get('is_active', False)])
                
                servers_html = self.utils.create_metric_card(
                    "🔧 Servers", 
                    f"{active_servers}/{server_count}",
                    f"{active_servers} Active"
                )
                st.markdown(servers_html, unsafe_allow_html=True)
            except Exception:
                st.metric("🔧 Servers", "0/0", delta="Error")
        
        with col3:
            # Get recent metrics
            try:
                metrics = asyncio.run(self.mongodb_client.get_usage_metrics(1))
                recent_sessions = metrics.get('summary', {}).get('total_sessions', 0)
                
                sessions_html = self.utils.create_metric_card(
                    "📊 Last Hour",
                    str(recent_sessions),
                    "Tool Calls"
                )
                st.markdown(sessions_html, unsafe_allow_html=True)
            except Exception:
                st.metric("📊 Last Hour", "0", delta="Error")
        
        with col4:
            last_refresh = self.utils.format_relative_time(st.session_state.last_refresh.isoformat())
            refresh_html = self.utils.create_metric_card(
                "🔄 Last Refresh",
                last_refresh,
                st.session_state.last_refresh.strftime("%H:%M:%S")
            )
            st.markdown(refresh_html, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render sidebar with controls."""
        st.sidebar.header("🎛️ Controls")
        
        # Refresh controls
        st.sidebar.subheader("Refresh Settings")
        st.session_state.auto_refresh = st.sidebar.checkbox(
            "Auto Refresh", 
            value=st.session_state.auto_refresh
        )
        
        st.session_state.refresh_interval = st.sidebar.slider(
            "Refresh Interval (seconds)", 
            min_value=10, 
            max_value=300, 
            value=st.session_state.refresh_interval,
            step=10
        )
        
        if st.sidebar.button("🔄 Refresh Now"):
            st.session_state.last_refresh = datetime.now()
            st.rerun()
        
        # Time range selector
        st.sidebar.subheader("📅 Time Range")
        time_range = st.sidebar.selectbox(
            "Select Time Range",
            ["1 Hour", "6 Hours", "24 Hours", "7 Days", "30 Days"],
            index=2
        )
        
        # Convert to hours
        time_range_hours = {
            "1 Hour": 1,
            "6 Hours": 6,
            "24 Hours": 24,
            "7 Days": 168,
            "30 Days": 720
        }
        st.session_state.time_range_hours = time_range_hours[time_range]
        
        # Server filter
        st.sidebar.subheader("🔧 Server Filter")
        try:
            servers = asyncio.run(self.mongodb_client.get_server_list())
            server_names = ["All Servers"] + [s["server_name"] for s in servers]
            selected_server = st.sidebar.selectbox("Select Server", server_names)
            st.session_state.selected_server = None if selected_server == "All Servers" else selected_server
        except Exception:
            st.sidebar.error("Failed to load servers")
            st.session_state.selected_server = None
    
    def render_main_content(self):
        """Render main dashboard content."""
        # Create tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Overview", 
            "🔧 Servers", 
            "📈 Tool Analytics", 
            "🏛️ Governance", 
            "📝 Tool Logs",
            "⚙️ System"
        ])
        
        with tab1:
            self.render_overview_tab()
        
        with tab2:
            self.render_servers_tab()
        
        with tab3:
            self.render_analytics_tab()
        
        with tab4:
            self.render_governance_tab()
        
        with tab5:
            self.render_tool_logs_tab()
        
        with tab6:
            self.render_system_tab()
    
    def render_overview_tab(self):
        """Render overview tab."""
        st.header("📊 System Overview")
        
        # Get metrics
        try:
            hours = st.session_state.time_range_hours
            metrics = asyncio.run(self.mongodb_client.get_usage_metrics(hours))
            summary = metrics.get('summary', {})
            
            # Key metrics using utility cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                card_html = self.utils.create_metric_card(
                    "📞 Total Sessions", 
                    str(summary.get('total_sessions', 0)),
                    f"Last {hours}h"
                )
                st.markdown(card_html, unsafe_allow_html=True)
            
            with col2:
                success_rate = summary.get('success_rate', 0)
                card_html = self.utils.create_metric_card(
                    "✅ Success Rate", 
                    f"{success_rate:.1f}%",
                    f"{summary.get('successful_sessions', 0)} successful",
                    "success"
                )
                st.markdown(card_html, unsafe_allow_html=True)
            
            with col3:
                avg_duration = summary.get('avg_duration_ms', 0)
                card_html = self.utils.create_metric_card(
                    "⏱️ Avg Duration", 
                    self.utils.format_duration(avg_duration),
                    "Per call"
                )
                st.markdown(card_html, unsafe_allow_html=True)
            
            with col4:
                unique_servers = summary.get('unique_servers', 0)
                card_html = self.utils.create_metric_card(
                    "🔧 Active Servers", 
                    str(unique_servers),
                    f"{summary.get('unique_tools', 0)} tools"
                )
                st.markdown(card_html, unsafe_allow_html=True)
            
            # Tool analytics overview
            st.subheader("Tool Usage Overview")
            analytics = asyncio.run(self.mongodb_client.get_tool_analytics(hours=hours))
            
            if analytics and not analytics.get('error'):
                tools = analytics.get('tools', [])
                if tools:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Success rate chart
                        analytics_summary = analytics.get('summary', {})
                        fig = self.utils.create_success_rate_chart(analytics_summary)
                        st.plotly_chart(
                            fig, 
                            use_container_width=True, 
                            key=self.get_unique_key("overview_success_chart")
                        )
                    
                    with col2:
                        # Tool usage chart
                        fig = self.utils.create_tool_usage_chart(tools, limit=10)
                        st.plotly_chart(
                            fig, 
                            use_container_width=True, 
                            key=self.get_unique_key("overview_usage_chart")
                        )
                else:
                    st.info("No tool usage data available for the selected time range.")
            else:
                st.info("No tool analytics data available.")
            
        except Exception as e:
            st.error(f"Failed to load overview data: {e}")
    
    def render_servers_tab(self):
        """Render servers management tab."""
        st.header("🔧 Server Management")
        
        try:
            servers = asyncio.run(self.mongodb_client.get_server_list())
            
            if not servers:
                st.info("No servers found in the database.")
                return
            
            # Server health chart
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Server Health Overview")
                health_fig = self.utils.create_server_health_chart(servers)
                st.plotly_chart(
                    health_fig, 
                    use_container_width=True,
                    key=self.get_unique_key("servers_health_chart")
                )
            
            with col2:
                st.subheader("Quick Stats")
                active_count = len([s for s in servers if s.get('is_active', False)])
                total_count = len(servers)
                
                avg_uptime = sum([
                    self.utils.calculate_uptime_percentage(s.get('registered_at', ''))
                    for s in servers if s.get('is_active', False)
                ]) / max(active_count, 1)
                
                st.metric("Total Servers", total_count)
                st.metric("Active Servers", active_count)
                st.metric("Average Uptime", f"{avg_uptime:.1f}%")
            
            # Server status table
            st.subheader("Server Status")
            
            server_data = []
            for server in servers:
                status = "active" if server.get("is_active", False) else "inactive"
                status_badge = self.utils.create_status_badge(status)
                mode_icon = self.utils.get_deployment_mode_icon(server.get("governance_mode", "unified"))
                registered_time = self.utils.format_relative_time(server.get("registered_at", ""))
                
                server_data.append({
                    "Server Name": server.get("server_name", "Unknown"),
                    "Status": status_badge,
                    "Mode": f"{mode_icon} {server.get('governance_mode', 'unified')}",
                    "Transport": server.get("transport", "Unknown"),
                    "Rate Limit": server.get("rate_limit", "Default"),
                    "Port": server.get("port", "N/A"),
                    "Registered": registered_time
                })
            
            df = pd.DataFrame(server_data)
            st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # Server details section
            st.subheader("Server Details")
            selected_server = st.selectbox(
                "Select server for details:",
                options=[s["server_name"] for s in servers],
                key=self.get_unique_key("server_select")
            )
            
            if selected_server:
                server_details = next((s for s in servers if s["server_name"] == selected_server), None)
                if server_details:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Configuration")
                        formatted_config = self.utils.format_server_config(server_details)
                        st.code(formatted_config, language='json')
                    
                    with col2:
                        st.subheader("Usage Statistics")
                        try:
                            usage = asyncio.run(self.mongodb_client.get_server_usage(
                                selected_server, st.session_state.time_range_hours
                            ))
                            
                            if usage and not usage.get('error') and usage.get('tools'):
                                tools_data = []
                                for tool in usage['tools']:
                                    tools_data.append({
                                        'Tool Name': tool.get('_id', 'Unknown'),
                                        'Usage Count': tool.get('usage_count', 0),
                                        'Success Count': tool.get('success_count', 0),
                                        'Avg Duration': self.utils.format_duration(tool.get('avg_duration', 0)),
                                        'Success Rate': f"{self.utils.calculate_success_rate(tool.get('success_count', 0), tool.get('usage_count', 0)):.1f}%"
                                    })
                                
                                tools_df = pd.DataFrame(tools_data)
                                st.dataframe(tools_df, use_container_width=True)
                            else:
                                st.info("No usage data available for this server.")
                        except Exception as e:
                            st.error(f"Failed to load server usage: {e}")
            
        except Exception as e:
            st.error(f"Failed to load server data: {e}")
    
    def render_analytics_tab(self):
        """Render tool analytics tab."""
        st.header("📈 Tool Analytics")
        
        try:
            hours = st.session_state.time_range_hours
            server_filter = st.session_state.selected_server
            
            analytics = asyncio.run(self.mongodb_client.get_tool_analytics(
                server_name=server_filter, hours=hours
            ))
            
            if analytics and not analytics.get('error'):
                # Summary statistics
                summary = analytics.get('summary', {})
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    card_html = self.utils.create_metric_card(
                        "🔧 Unique Tools", 
                        str(summary.get('total_unique_tools', 0))
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col2:
                    card_html = self.utils.create_metric_card(
                        "📞 Total Calls", 
                        str(summary.get('total_calls', 0))
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col3:
                    card_html = self.utils.create_metric_card(
                        "✅ Success Rate", 
                        f"{summary.get('overall_success_rate', 0):.1f}%",
                        card_type="success"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col4:
                    most_used = summary.get('most_used_tool', {})
                    most_used_name = f"{most_used.get('server_name', 'N/A')}.{most_used.get('tool_name', 'N/A')}" if most_used else 'N/A'
                    card_html = self.utils.create_metric_card(
                        "🏆 Most Used Tool", 
                        most_used_name[:20] + "..." if len(most_used_name) > 20 else most_used_name
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                # Tool details with visualizations
                tools = analytics.get('tools', [])
                if tools:
                    st.subheader("Tool Performance Analysis")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Tool usage chart
                        fig = self.utils.create_tool_usage_chart(tools, limit=15)
                        st.plotly_chart(
                            fig, 
                            use_container_width=True,
                            key=self.get_unique_key("analytics_usage_chart")
                        )
                    
                    with col2:
                        # Performance scatter plot
                        fig = self.utils.create_performance_scatter(tools)
                        st.plotly_chart(
                            fig, 
                            use_container_width=True,
                            key=self.get_unique_key("analytics_scatter_chart")
                        )
                    
                    # Detailed table
                    st.subheader("Detailed Performance Metrics")
                    
                    tools_data = []
                    for tool in tools:
                        tools_data.append({
                            'Server': tool['server_name'],
                            'Tool': tool['tool_name'],
                            'Total Calls': tool['total_calls'],
                            'Success Rate': f"{tool['success_rate']:.1f}%",
                            'Avg Duration': self.utils.format_duration(tool['avg_duration_ms']),
                            'Max Duration': self.utils.format_duration(tool['max_duration_ms']),
                            'Min Duration': self.utils.format_duration(tool['min_duration_ms']),
                            'Avg Output Size': self.utils.format_size(tool['avg_output_size'] or 0),
                            'Status': self.utils.get_status_icon('success' if tool['success_rate'] > 90 else 'warning' if tool['success_rate'] > 50 else 'error')
                        })
                    
                    df = pd.DataFrame(tools_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No tool data available for the selected filters.")
            else:
                st.info("No tool analytics data available for the selected filters.")
                
        except Exception as e:
            st.error(f"Failed to load analytics data: {e}")
    
    def render_governance_tab(self):
        """Render governance monitoring tab."""
        st.header("🏛️ Governance Monitoring")
        
        try:
            hours = st.session_state.time_range_hours
            
            # Get governance metrics
            gov_metrics = asyncio.run(self.mongodb_client.get_governance_metrics(hours))
            
            if gov_metrics and not gov_metrics.get('error'):
                # Governance overview
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    card_html = self.utils.create_metric_card(
                        "⚖️ Total Decisions", 
                        str(gov_metrics.get('total_decisions', 0))
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col2:
                    card_html = self.utils.create_metric_card(
                        "✅ Allowed", 
                        str(gov_metrics.get('allowed_decisions', 0)),
                        card_type="success"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col3:
                    denied_count = gov_metrics.get('denied_decisions', 0)
                    card_type = "error" if denied_count > 0 else "default"
                    card_html = self.utils.create_metric_card(
                        "🚫 Denied", 
                        str(denied_count),
                        card_type=card_type
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col4:
                    approval_rate = gov_metrics.get('approval_rate', 100)
                    card_type = "success" if approval_rate > 90 else "warning" if approval_rate > 70 else "error"
                    card_html = self.utils.create_metric_card(
                        "📊 Approval Rate", 
                        f"{approval_rate:.1f}%",
                        card_type=card_type
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.info("No governance metrics available.")
            
            # Violations analysis
            violations = asyncio.run(self.mongodb_client.get_governance_violations(hours))
            
            if violations:
                st.subheader("🚨 Governance Analysis")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Violation types chart
                    violation_types = [v.get('policy_violation', 'unknown') for v in violations]
                    violation_counts = pd.Series(violation_types).value_counts()
                    
                    fig = px.pie(
                        values=violation_counts.values,
                        names=violation_counts.index,
                        title="Violation Types Distribution",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    st.plotly_chart(
                        fig, 
                        use_container_width=True,
                        key=self.get_unique_key("governance_violations_pie")
                    )
                
                with col2:
                    # Violations by server
                    server_violations = [v.get('server_name', 'unknown') for v in violations]
                    server_counts = pd.Series(server_violations).value_counts()
                    
                    fig = px.bar(
                        x=server_counts.values,
                        y=server_counts.index,
                        orientation='h',
                        title='Violations by Server'
                    )
                    st.plotly_chart(
                        fig, 
                        use_container_width=True,
                        key=self.get_unique_key("governance_violations_bar")
                    )
                
                # Violations table
                st.subheader("Recent Violations")
                violations_data = []
                for violation in violations[:50]:  # Show last 50
                    status_icon = self.utils.get_status_icon(violation.get('policy_violation', 'error'))
                    formatted_time = self.utils.format_timestamp(violation.get('timestamp', ''))
                    relative_time = self.utils.format_relative_time(violation.get('timestamp', ''))
                    
                    violations_data.append({
                        'Status': status_icon,
                        'Time': formatted_time,
                        'Relative': relative_time,
                        'Server': violation.get('server_name', 'Unknown'),
                        'Tool': violation.get('tool_name', 'Unknown'),
                        'Violation': violation.get('policy_violation', 'Unknown'),
                        'Source': violation.get('source', 'Unknown'),
                        'Reason': (violation.get('reason', 'Unknown')[:80] + '...') if len(violation.get('reason', '')) > 80 else violation.get('reason', 'Unknown')
                    })
                
                df = pd.DataFrame(violations_data)
                st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                
            else:
                st.success("🎉 No governance violations found in the selected time range!")
                
        except Exception as e:
            st.error(f"Failed to load governance data: {e}")
    
    def render_tool_logs_tab(self):
        """Render tool logs tab."""
        st.header("📝 Tool Execution Logs")
        
        try:
            hours = st.session_state.time_range_hours
            server_filter = st.session_state.selected_server
            
            # Enhanced filters
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                session_filter = st.text_input("Session ID Filter", key=self.get_unique_key("session_filter"))
            
            with col2:
                tool_filter = st.text_input("Tool Name Filter", key=self.get_unique_key("tool_filter"))
            
            with col3:
                status_filter = st.selectbox("Status Filter", ["All", "success", "error", "denied"], key=self.get_unique_key("status_filter"))
            
            with col4:
                limit = st.number_input("Max Results", min_value=10, max_value=1000, value=100, key=self.get_unique_key("limit_input"))
            
            # Get tool logs
            logs = asyncio.run(self.mongodb_client.get_tool_logs(
                server_name=server_filter,
                tool_name=tool_filter if tool_filter else None,
                session_id=session_filter if session_filter else None,
                hours=hours,
                limit=limit
            ))
            
            # Apply additional filtering
            filter_criteria = {}
            if status_filter != "All":
                filter_criteria['status'] = status_filter
            
            if filter_criteria:
                logs = self.utils.filter_logs_by_criteria(logs, filter_criteria)
            
            if logs:
                # Log statistics
                st.subheader("📊 Log Statistics")
                
                total_logs = len(logs)
                success_logs = len([log for log in logs if log.get('status') == 'success'])
                error_logs = len([log for log in logs if log.get('status') == 'error'])
                denied_logs = len([log for log in logs if log.get('status') == 'denied'])
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    card_html = self.utils.create_metric_card("Total Logs", str(total_logs))
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col2:
                    success_rate = self.utils.calculate_success_rate(success_logs, total_logs)
                    card_html = self.utils.create_metric_card(
                        "Success", 
                        str(success_logs), 
                        f"{success_rate:.1f}%",
                        "success"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col3:
                    error_rate = (error_logs / total_logs) * 100 if total_logs > 0 else 0
                    card_html = self.utils.create_metric_card(
                        "Errors", 
                        str(error_logs), 
                        f"{error_rate:.1f}%",
                        "error"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                with col4:
                    denied_rate = (denied_logs / total_logs) * 100 if total_logs > 0 else 0
                    card_html = self.utils.create_metric_card(
                        "Denied", 
                        str(denied_logs),
                        f"{denied_rate:.1f}%",
                        "warning"
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                
                # Detailed logs
                st.subheader("📋 Log Details")
                
                for log in logs:
                    status = log.get('status', 'unknown')
                    timestamp = log.get('timestamp', '')
                    server_name = log.get('server_name', 'Unknown')
                    tool_name = log.get('tool_name', 'Unknown')
                    session_id = log.get('session_id', 'N/A')
                    duration = log.get('duration_ms', 0)
                    
                    status_icon = self.utils.get_status_icon(status)
                    formatted_time = self.utils.format_timestamp(timestamp)
                    relative_time = self.utils.format_relative_time(timestamp)
                    formatted_duration = self.utils.format_duration(duration)
                    
                    # Create expandable log entry
                    with st.expander(f"{status_icon} {formatted_time} - {server_name}.{tool_name} ({formatted_duration}) - {relative_time}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Status:** {self.utils.create_status_badge(status)}", unsafe_allow_html=True)
                            st.write(f"**Server:** {server_name}")
                            st.write(f"**Tool:** {tool_name}")
                            st.write(f"**Session ID:** {session_id}")
                            st.write(f"**Duration:** {formatted_duration}")
                            st.write(f"**Time:** {relative_time}")
                            
                            if log.get('error_message'):
                                st.write(f"**Error:** {log['error_message']}")
                        
                        with col2:
                            # Inputs and outputs
                            inputs = log.get('inputs', {})
                            outputs = log.get('outputs', {})
                            
                            if inputs and inputs != {"_tracked": False}:
                                st.write("**Inputs:**")
                                if inputs.get('_truncated'):
                                    original_size = self.utils.format_size(inputs.get('_original_size', 0))
                                    st.warning(f"Inputs truncated (original size: {original_size})")
                                else:
                                    sanitized_inputs = self.utils.sanitize_data_for_display(inputs)
                                    st.json(sanitized_inputs)
                            
                            if outputs:
                                st.write("**Outputs:**")
                                if isinstance(outputs, dict) and outputs.get('_truncated'):
                                    original_size = self.utils.format_size(outputs.get('_original_size', 0))
                                    st.warning(f"Outputs truncated (original size: {original_size})")
                                else:
                                    sanitized_outputs = self.utils.sanitize_data_for_display(outputs)
                                    st.json(sanitized_outputs)
                
                # Pagination info
                if len(logs) >= limit:
                    st.info(f"Showing {limit} most recent logs. Increase limit or refine filters to see more.")
                
            else:
                st.info("No tool logs found for the selected filters.")
                
        except Exception as e:
            st.error(f"Failed to load tool logs: {e}")
    
    def render_system_tab(self):
        """Render system monitoring tab."""
        st.header("⚙️ System Monitoring")
        
        # Database status
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Database Connection")
            try:
                # Test MongoDB connection
                self.mongodb_client.client.admin.command('ping')
                
                connection_html = self.utils.create_metric_card(
                    "Database Status", 
                    "Connected", 
                    "✅ MongoDB Atlas",
                    "success"
                )
                st.markdown(connection_html, unsafe_allow_html=True)
                
                # Database stats
                db_stats = self.mongodb_client.database.command("dbStats")
                db_size = self.utils.format_size(db_stats.get('dataSize', 0))
                
                st.metric("Database Size", db_size)
                st.metric("Collections", db_stats.get('collections', 0))
                st.metric("Indexes", db_stats.get('indexes', 0))
                
            except Exception as e:
                error_html = self.utils.create_metric_card(
                    "Database Status", 
                    "Failed", 
                    f"❌ {str(e)[:50]}...",
                    "error"
                )
                st.markdown(error_html, unsafe_allow_html=True)
        
        with col2:
            st.subheader("Collection Statistics")
            try:
                collections = [
                    "tool_logs",
                    "servers", 
                    "governance_logs",
                    "server_tools",
                    "governance_configs",
                    "deployments"
                ]
                
                collection_stats = []
                for collection_name in collections:
                    try:
                        count = self.mongodb_client.database[collection_name].count_documents({})
                        collection_stats.append({
                            'Collection': collection_name,
                            'Documents': count,
                            'Status': self.utils.get_status_icon('success' if count > 0 else 'warning')
                        })
                    except Exception:
                        collection_stats.append({
                            'Collection': collection_name,
                            'Documents': 'Error',
                            'Status': self.utils.get_status_icon('error')
                        })
                
                df = pd.DataFrame(collection_stats)
                st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                        
            except Exception as e:
                st.error(f"Failed to get collection stats: {e}")
        
        # System configuration
        st.subheader("System Configuration")
        
        config_info = {
            "auto_refresh": st.session_state.auto_refresh,
            "refresh_interval_seconds": st.session_state.refresh_interval,
            "time_range_hours": st.session_state.time_range_hours,
            "selected_server": st.session_state.selected_server or "All Servers",
            "dashboard_started": st.session_state.get('start_time', 'Unknown'),
            "last_refresh": st.session_state.last_refresh.isoformat()
        }
        
        formatted_config = self.utils.format_server_config(config_info)
        st.code(formatted_config, language='json')
        
        # System actions
        st.subheader("System Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🧹 Clear Cache", key=self.get_unique_key("clear_cache")):
                cache_keys = [key for key in st.session_state.keys() 
                             if key not in ['auto_refresh', 'refresh_interval', 'start_time']]
                cleared_count = 0
                for key in cache_keys:
                    if key.startswith('cache_'):
                        del st.session_state[key]
                        cleared_count += 1
                
                if cleared_count > 0:
                    st.success(f"✅ Cleared {cleared_count} cache items!")
                else:
                    st.info("No cache items to clear")
        
        with col2:
            if st.button("📊 Export Data", key=self.get_unique_key("export_data")):
                try:
                    hours = 24
                    export_data = {
                        'export_info': {
                            'timestamp': datetime.now().isoformat(),
                            'time_range_hours': hours,
                            'exported_by': 'MCP Governance Dashboard'
                        },
                        'usage_metrics': asyncio.run(self.mongodb_client.get_usage_metrics(hours)),
                        'servers': asyncio.run(self.mongodb_client.get_server_list()),
                    }
                    
                    try:
                        export_data['tool_analytics'] = asyncio.run(self.mongodb_client.get_tool_analytics(hours=hours))
                    except Exception:
                        pass
                    
                    try:
                        export_data['governance_metrics'] = asyncio.run(self.mongodb_client.get_governance_metrics(hours))
                    except Exception:
                        pass
                    
                    try:
                        export_data['recent_violations'] = asyncio.run(self.mongodb_client.get_governance_violations(hours))
                    except Exception:
                        pass
                    
                    sanitized_data = self.utils.sanitize_data_for_display(export_data)
                    export_json = json.dumps(sanitized_data, indent=2, default=str)
                    file_size = self.utils.format_size(len(export_json.encode('utf-8')))
                    
                    st.download_button(
                        label=f"📥 Download Export ({file_size})",
                        data=export_json,
                        file_name=f"mcp_governance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key=self.get_unique_key("download_export")
                    )
                    
                    st.success("✅ Export data prepared!")
                    
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")
        
        with col3:
            if st.button("🔄 Force Refresh", key=self.get_unique_key("force_refresh")):
                st.session_state.last_refresh = datetime.now()
                st.success("✅ Dashboard refreshed!")
                st.rerun()
    
    def handle_auto_refresh(self):
        """Handle auto refresh functionality."""
        if st.session_state.auto_refresh:
            current_time = time.time()
            last_refresh_time = getattr(st.session_state, 'last_auto_refresh', current_time)
            
            if current_time - last_refresh_time >= st.session_state.refresh_interval:
                st.session_state.last_refresh = datetime.now()
                st.session_state.last_auto_refresh = current_time
                st.rerun()

def main():
    """Main dashboard function."""
    # Initialize session state
    if 'start_time' not in st.session_state:
        st.session_state.start_time = datetime.now().isoformat()
    
    # Create and run dashboard
    try:
        dashboard = MCPGovernanceDashboard()
        dashboard.run()
    except Exception as e:
        st.error(f"Dashboard error: {e}")
        st.exception(e)
        st.info("Trying to reconnect...")
        time.sleep(2)
        st.rerun()

if __name__ == "__main__":
    main()