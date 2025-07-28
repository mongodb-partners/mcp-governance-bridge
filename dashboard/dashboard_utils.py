# dashboard/dashboard_utils.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import re
import uuid

class DashboardUtils:
    """Utility functions for dashboard operations."""
    
    def __init__(self):
        self.color_palette = {
            'primary': '#667eea',
            'secondary': '#764ba2',
            'success': '#28a745',
            'error': '#dc3545',
            'warning': '#ffc107',
            'info': '#17a2b8',
            'dark': '#343a40',
            'light': '#f8f9fa'
        }
        self._chart_counter = 0
    
    def get_unique_chart_key(self, prefix: str = "chart") -> str:
        """Generate unique key for charts."""
        self._chart_counter += 1
        return f"{prefix}_{self._chart_counter}_{uuid.uuid4().hex[:8]}"
    
    def format_duration(self, milliseconds: float) -> str:
        """Format duration in milliseconds to human readable string."""
        if milliseconds is None:
            return "N/A"
        
        if milliseconds < 1000:
            return f"{milliseconds:.0f}ms"
        elif milliseconds < 60000:
            return f"{milliseconds/1000:.1f}s"
        elif milliseconds < 3600000:
            return f"{milliseconds/60000:.1f}m"
        else:
            return f"{milliseconds/3600000:.1f}h"
    
    def format_timestamp(self, timestamp: str) -> str:
        """Format ISO timestamp to human readable string."""
        if not timestamp:
            return "Unknown"
        
        try:
            if isinstance(timestamp, str):
                timestamp = timestamp.replace('Z', '+00:00')
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = timestamp
            
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            
            if diff.days > 0:
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            elif diff.seconds > 3600:
                return dt.strftime("%H:%M:%S")
            else:
                return dt.strftime("%H:%M:%S")
                
        except Exception:
            return str(timestamp)
    
    def format_relative_time(self, timestamp: str) -> str:
        """Format timestamp as relative time (e.g., '2 hours ago')."""
        if not timestamp:
            return "Unknown"
        
        try:
            if isinstance(timestamp, str):
                timestamp = timestamp.replace('Z', '+00:00')
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = timestamp
            
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                return "Just now"
                
        except Exception:
            return "Unknown"
    
    def format_size(self, bytes_size: int) -> str:
        """Format bytes to human readable size."""
        if bytes_size is None:
            return "N/A"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}TB"
    
    def calculate_success_rate(self, successful: int, total: int) -> float:
        """Calculate success rate percentage."""
        if total == 0:
            return 0.0
        return (successful / total) * 100
    
    def create_status_badge(self, status: str) -> str:
        """Create HTML badge for status."""
        status_colors = {
            'active': '#28a745',
            'inactive': '#dc3545',
            'success': '#28a745',
            'error': '#dc3545',
            'denied': '#ffc107',
            'warning': '#ffc107',
            'running': '#17a2b8',
            'pending': '#6c757d'
        }
        
        color = status_colors.get(status.lower(), '#6c757d')
        return f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">{status.title()}</span>'
    
    def create_metric_card(self, title: str, value: str, delta: Optional[str] = None, 
                          card_type: str = 'default') -> str:
        """Create HTML metric card."""
        type_classes = {
            'default': 'metric-card',
            'success': 'metric-card success-metric',
            'error': 'metric-card error-metric',
            'warning': 'metric-card warning-metric'
        }
        
        card_class = type_classes.get(card_type, 'metric-card')
        delta_html = f'<small>{delta}</small>' if delta else ''
        
        return f"""
        <div class="{card_class}">
            <h3>{title}</h3>
            <h2>{value}</h2>
            {delta_html}
        </div>
        """
    
    def create_tool_usage_chart(self, tool_data: List[Dict[str, Any]], limit: int = 20) -> go.Figure:
        """Create tool usage chart."""
        if not tool_data:
            fig = go.Figure()
            fig.update_layout(title="No tool usage data available")
            return fig
        
        # Sort by usage count and take top N
        sorted_tools = sorted(tool_data, key=lambda x: x.get('total_calls', 0), reverse=True)[:limit]
        
        tool_names = [f"{tool['server_name']}.{tool['tool_name']}" for tool in sorted_tools]
        usage_counts = [tool['total_calls'] for tool in sorted_tools]
        success_rates = [tool['success_rate'] for tool in sorted_tools]
        
        fig = px.bar(
            x=usage_counts,
            y=tool_names,
            orientation='h',
            title=f'Top {len(sorted_tools)} Tools by Usage',
            color=success_rates,
            color_continuous_scale='RdYlGn',
            labels={'x': 'Total Calls', 'y': 'Tool', 'color': 'Success Rate (%)'}
        )
        
        fig.update_layout(
            height=max(400, len(sorted_tools) * 25),
            coloraxis_colorbar=dict(title="Success Rate (%)")
        )
        
        return fig
    
    def create_success_rate_chart(self, success_data: Dict[str, Any]) -> go.Figure:
        """Create success rate pie chart."""
        successful = success_data.get('total_successful', 0) or success_data.get('successful_calls', 0)
        failed = success_data.get('total_failed', 0) or success_data.get('failed_calls', 0)
        denied = success_data.get('total_denied', 0) or success_data.get('denied_calls', 0)
        
        if successful + failed + denied == 0:
            fig = go.Figure()
            fig.update_layout(title="No data available")
            return fig
        
        labels = []
        values = []
        colors = []
        
        if successful > 0:
            labels.append('Success')
            values.append(successful)
            colors.append(self.color_palette['success'])
        
        if failed > 0:
            labels.append('Failed')
            values.append(failed)
            colors.append(self.color_palette['error'])
        
        if denied > 0:
            labels.append('Denied')
            values.append(denied)
            colors.append(self.color_palette['warning'])
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.3,
            marker_colors=colors
        )])
        
        total = successful + failed + denied
        success_rate = (successful / total) * 100 if total > 0 else 0
        
        fig.update_layout(
            title="Execution Results Distribution",
            annotations=[dict(
                text=f"{success_rate:.1f}%", 
                x=0.5, y=0.5, 
                font_size=20, 
                showarrow=False
            )]
        )
        
        return fig
    
    def create_timeline_chart(self, timeline_data: List[Dict[str, Any]], 
                             time_column: str = 'timestamp',
                             value_column: str = 'count') -> go.Figure:
        """Create timeline chart for usage patterns."""
        if not timeline_data:
            fig = go.Figure()
            fig.update_layout(title="No timeline data available")
            return fig
        
        df = pd.DataFrame(timeline_data)
        
        # Convert timestamp column to datetime
        df[time_column] = pd.to_datetime(df[time_column])
        
        # Group by time intervals if needed
        if len(df) > 100:  # Too many points, group by hour
            df = df.set_index(time_column).resample('1H')[value_column].sum().reset_index()
        
        fig = px.line(
            df,
            x=time_column,
            y=value_column,
            title='Activity Over Time',
            line_shape='spline'
        )
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Activity Count",
            height=400
        )
        
        return fig
    
    def create_server_health_chart(self, servers: List[Dict[str, Any]]) -> go.Figure:
        """Create server health status chart."""
        if not servers:
            fig = go.Figure()
            fig.update_layout(title="No server data available")
            return fig
        
        active_count = len([s for s in servers if s.get('is_active', False)])
        inactive_count = len(servers) - active_count
        
        fig = go.Figure(data=[go.Pie(
            labels=['Active', 'Inactive'],
            values=[active_count, inactive_count],
            hole=0.3,
            marker_colors=[self.color_palette['success'], self.color_palette['error']]
        )])
        
        fig.update_layout(
            title="Server Health Status",
            annotations=[dict(
                text=f"{active_count}/{len(servers)}", 
                x=0.5, y=0.5, 
                font_size=20, 
                showarrow=False
            )]
        )
        
        return fig
    
    def create_violation_heatmap(self, violations: List[Dict[str, Any]]) -> go.Figure:
        """Create heatmap of violations by server and time."""
        if not violations:
            fig = go.Figure()
            fig.update_layout(title="No violations data available")
            return fig
        
        # Convert to DataFrame
        df = pd.DataFrame(violations)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        
        # Create pivot table
        pivot = df.pivot_table(
            values='policy_violation', 
            index='server_name', 
            columns='hour', 
            aggfunc='count', 
            fill_value=0
        )
        
        fig = px.imshow(
            pivot,
            title="Violations Heatmap (by Server and Hour)",
            labels={'x': 'Hour of Day', 'y': 'Server', 'color': 'Violation Count'},
            color_continuous_scale='Reds'
        )
        
        return fig
    
    def sanitize_data_for_display(self, data: Any, max_length: int = 100) -> Any:
        """Sanitize data for safe display."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in ['password', 'token', 'secret', 'key', 'private_key', 'auth']:
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = self.sanitize_data_for_display(value, max_length)
            return sanitized
        
        elif isinstance(data, list):
            return [self.sanitize_data_for_display(item, max_length) for item in data]
        
        elif isinstance(data, str):
            if len(data) > max_length:
                return data[:max_length] + "..."
            return data
        
        else:
            return data
    
    def format_server_config(self, server_config: Dict[str, Any]) -> str:
        """Format server configuration for display."""
        try:
            # Sanitize the config
            safe_config = self.sanitize_data_for_display(server_config)
            return json.dumps(safe_config, indent=2)
        except Exception:
            return str(server_config)
    
    def get_deployment_mode_icon(self, mode: str) -> str:
        """Get icon for deployment mode."""
        mode_icons = {
            'unified': '🌐',
            'multi-port': '🔧',
            'hybrid': '🔀',
            'standalone': '🏗️',
            'cluster': '🏢'
        }
        return mode_icons.get(mode.lower(), '⚙️')
    
    def get_status_icon(self, status: str) -> str:
        """Get icon for status."""
        status_icons = {
            'active': '🟢',
            'inactive': '🔴',
            'success': '✅',
            'error': '❌',
            'denied': '🚫',
            'warning': '⚠️',
            'running': '🏃',
            'pending': '⏳'
        }
        return status_icons.get(status.lower(), '❓')
    
    def calculate_uptime_percentage(self, start_time: str, current_time: str = None) -> float:
        """Calculate uptime percentage."""
        try:
            if current_time is None:
                current_time = datetime.now().isoformat()
            
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
            
            # For now, assume 100% uptime if server is active
            return 100.0
            
        except Exception:
            return 0.0
    
    def create_performance_scatter(self, tools_data: List[Dict[str, Any]]) -> go.Figure:
        """Create performance scatter plot."""
        if not tools_data:
            fig = go.Figure()
            fig.update_layout(title="No performance data available")
            return fig
        
        df = pd.DataFrame(tools_data)
        
        fig = px.scatter(
            df,
            x='total_calls',
            y='avg_duration_ms',
            size='successful_calls',
            color='success_rate',
            hover_data=['server_name', 'tool_name'],
            title='Tool Performance Analysis',
            labels={
                'total_calls': 'Total Calls',
                'avg_duration_ms': 'Average Duration (ms)',
                'success_rate': 'Success Rate (%)'
            },
            color_continuous_scale='RdYlGn'
        )
        
        fig.update_layout(height=500)
        return fig
    
    def filter_logs_by_criteria(self, logs: List[Dict[str, Any]], 
                               criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter logs based on criteria."""
        filtered = logs
        
        if criteria.get('server_name'):
            filtered = [log for log in filtered if log.get('server_name') == criteria['server_name']]
        
        if criteria.get('tool_name'):
            filtered = [log for log in filtered if criteria['tool_name'] in log.get('tool_name', '')]
        
        if criteria.get('status'):
            filtered = [log for log in filtered if log.get('status') == criteria['status']]
        
        if criteria.get('session_id'):
            filtered = [log for log in filtered if log.get('session_id') == criteria['session_id']]
        
        return filtered
    
    def get_color_for_status(self, status: str) -> str:
        """Get color for status."""
        status_colors = {
            'success': self.color_palette['success'],
            'error': self.color_palette['error'],
            'denied': self.color_palette['warning'],
            'active': self.color_palette['success'],
            'inactive': self.color_palette['error']
        }
        return status_colors.get(status.lower(), self.color_palette['dark'])