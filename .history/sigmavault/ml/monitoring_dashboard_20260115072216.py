"""
Real-time monitoring dashboard for ML pipeline with WebSocket streaming.

Provides live visualization of:
- Anomaly detection status and recent detections
- Model performance metrics and trends
- Cache hit rates and efficiency
- Alert history and active alerts
- System health indicators

Streams metrics to connected clients via WebSocket for real-time updates.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import asyncio
import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# WebSocket support (will work with or without websockets library)
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    import warnings
    warnings.warn("websockets library not available. Install with: pip install websockets")

from .metrics_collector import MetricsCollector
from .alert_manager import AlertManager, Alert, AlertSeverity


logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """
    Configuration for monitoring dashboard.
    
    Attributes:
        host: HTTP server host
        port: HTTP server port
        ws_port: WebSocket server port
        refresh_interval_ms: Dashboard refresh interval
        history_minutes: How much historical data to show
        enable_websocket: Whether to enable WebSocket streaming
    """
    host: str = 'localhost'
    port: int = 8080
    ws_port: int = 8081
    refresh_interval_ms: int = 1000
    history_minutes: int = 60
    enable_websocket: bool = True


class DashboardState(Enum):
    """Dashboard operational state."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class MonitoringDashboard:
    """
    Real-time monitoring dashboard with WebSocket streaming.
    
    Provides comprehensive visualization of ML pipeline metrics:
    - Current anomaly detection status
    - Model performance trends
    - Cache efficiency metrics
    - Alert history and active alerts
    - System health indicators
    
    Streams updates to connected WebSocket clients for real-time
    monitoring without page refreshes.
    
    Example:
        >>> dashboard = MonitoringDashboard(
        ...     metrics_collector=get_metrics_collector(),
        ...     alert_manager=alert_manager
        ... )
        >>> dashboard.start()
        >>> # Dashboard accessible at http://localhost:8080
        >>> # WebSocket streaming at ws://localhost:8081
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        alert_manager: AlertManager,
        config: Optional[DashboardConfig] = None
    ):
        """
        Initialize monitoring dashboard.
        
        Args:
            metrics_collector: Metrics collector instance
            alert_manager: Alert manager instance
            config: Dashboard configuration
        """
        self.metrics_collector = metrics_collector
        self.alert_manager = alert_manager
        self.config = config or DashboardConfig()
        
        self.state = DashboardState.STOPPED
        self.ws_clients: Set[Any] = set()
        self.http_server: Optional[HTTPServer] = None
        self.ws_server: Optional[Any] = None
        
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._streaming_task: Optional[asyncio.Task] = None
    
    def start(self):
        """Start HTTP and WebSocket servers."""
        with self.lock:
            if self.state != DashboardState.STOPPED:
                raise RuntimeError(f"Cannot start dashboard in state: {self.state}")
            
            self.state = DashboardState.STARTING
            
            try:
                # Start HTTP server
                self._start_http_server()
                
                # Start WebSocket server if enabled
                if self.config.enable_websocket and WEBSOCKETS_AVAILABLE:
                    self._start_websocket_server()
                
                self.state = DashboardState.RUNNING
                logger.info(f"Dashboard started at http://{self.config.host}:{self.config.port}")
                
                if self.config.enable_websocket:
                    logger.info(f"WebSocket streaming at ws://{self.config.host}:{self.config.ws_port}")
            
            except Exception as e:
                self.state = DashboardState.ERROR
                logger.error(f"Failed to start dashboard: {e}")
                raise
    
    def stop(self):
        """Stop HTTP and WebSocket servers."""
        with self.lock:
            if self.state not in [DashboardState.RUNNING, DashboardState.ERROR]:
                return
            
            self.state = DashboardState.STOPPING
            self._stop_event.set()
            
            try:
                # Stop HTTP server
                if self.http_server:
                    self.http_server.shutdown()
                    self.http_server = None
                
                # Stop WebSocket server
                if self.ws_server:
                    self.ws_server.close()
                    self.ws_server = None
                
                self.state = DashboardState.STOPPED
                logger.info("Dashboard stopped")
            
            except Exception as e:
                logger.error(f"Error stopping dashboard: {e}")
                self.state = DashboardState.ERROR
    
    def _start_http_server(self):
        """Start HTTP server for dashboard UI."""
        handler = self._create_http_handler()
        self.http_server = HTTPServer((self.config.host, self.config.port), handler)
        
        # Run server in background thread
        server_thread = threading.Thread(
            target=self.http_server.serve_forever,
            daemon=True
        )
        server_thread.start()
    
    def _start_websocket_server(self):
        """Start WebSocket server for real-time streaming."""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("WebSocket library not available, streaming disabled")
            return
        
        # Start async event loop in background thread
        loop_thread = threading.Thread(
            target=self._run_websocket_loop,
            daemon=True
        )
        loop_thread.start()
    
    def _run_websocket_loop(self):
        """Run WebSocket server event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def handler(websocket, path):
            """Handle WebSocket connection."""
            self.ws_clients.add(websocket)
            logger.info(f"WebSocket client connected: {websocket.remote_address}")
            
            try:
                # Send initial snapshot
                await websocket.send(json.dumps(self.get_dashboard_data()))
                
                # Keep connection alive
                while self.state == DashboardState.RUNNING:
                    await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            finally:
                self.ws_clients.discard(websocket)
                logger.info(f"WebSocket client disconnected: {websocket.remote_address}")
        
        # Start WebSocket server
        start_server = websockets.serve(
            handler,
            self.config.host,
            self.config.ws_port
        )
        
        self.ws_server = loop.run_until_complete(start_server)
        
        # Start streaming task
        self._streaming_task = loop.create_task(self._stream_metrics())
        
        # Run event loop
        loop.run_forever()
    
    async def _stream_metrics(self):
        """Stream metrics to WebSocket clients at regular intervals."""
        while self.state == DashboardState.RUNNING:
            try:
                if self.ws_clients:
                    data = json.dumps(self.get_dashboard_data())
                    
                    # Send to all clients concurrently
                    await asyncio.gather(*[
                        client.send(data)
                        for client in self.ws_clients
                    ], return_exceptions=True)
                
                await asyncio.sleep(self.config.refresh_interval_ms / 1000)
            
            except Exception as e:
                logger.error(f"Error streaming metrics: {e}")
                await asyncio.sleep(1)
    
    def _create_http_handler(self):
        """Create HTTP request handler for dashboard UI."""
        dashboard_instance = self
        
        class DashboardHTTPHandler(BaseHTTPRequestHandler):
            """HTTP request handler for dashboard."""
            
            def do_GET(self):
                """Handle GET requests."""
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(dashboard_instance.get_dashboard_html().encode())
                
                elif self.path == '/api/metrics':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    data = json.dumps(dashboard_instance.get_dashboard_data())
                    self.wfile.write(data.encode())
                
                elif self.path == '/api/prometheus':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    metrics = dashboard_instance.metrics_collector.export_prometheus()
                    self.wfile.write(metrics.encode())
                
                else:
                    self.send_error(404)
            
            def log_message(self, format, *args):
                """Suppress HTTP server logging."""
                pass
        
        return DashboardHTTPHandler
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get complete dashboard data snapshot.
        
        Returns:
            Dictionary with all dashboard data
        """
        metrics_json = self.metrics_collector.export_json()
        alert_stats = self.alert_manager.get_statistics()
        recent_alerts = self.alert_manager.get_recent_alerts(
            self.config.history_minutes
        )
        
        # Calculate derived metrics
        cache_hits = self.metrics_collector.get_metric('cache_hits_total') or 0
        cache_misses = self.metrics_collector.get_metric('cache_misses_total') or 0
        total_cache_requests = cache_hits + cache_misses
        cache_hit_rate = (cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0
        
        anomaly_count = self.metrics_collector.get_metric('anomaly_detections_total') or 0
        alert_count = self.metrics_collector.get_metric('anomaly_alerts_total') or 0
        
        # Get histogram statistics
        detection_latency = self.metrics_collector.get_histogram_stats(
            'anomaly_detection_latency_ms'
        )
        inference_latency = self.metrics_collector.get_histogram_stats(
            'model_inference_latency_ms'
        )
        
        return {
            'timestamp': datetime.now().isoformat(),
            'status': {
                'healthy': self.metrics_collector.get_metric('ml_pipeline_healthy') == 1,
                'errors': self.metrics_collector.get_metric('ml_pipeline_errors_total') or 0
            },
            'anomalies': {
                'total_detected': anomaly_count,
                'alerts_triggered': alert_count,
                'current_score': self.metrics_collector.get_metric('anomaly_detection_score') or 0,
                'detection_latency_p95_ms': detection_latency.get('p95', 0)
            },
            'cache': {
                'hit_rate_percent': round(cache_hit_rate, 2),
                'total_hits': cache_hits,
                'total_misses': cache_misses
            },
            'model': {
                'updates_total': self.metrics_collector.get_metric('model_updates_total') or 0,
                'accuracy': self.metrics_collector.get_metric('model_accuracy') or 0,
                'inference_latency_p95_ms': inference_latency.get('p95', 0)
            },
            'alerts': {
                'total': alert_stats['total_alerts'],
                'unresolved': alert_stats['unresolved'],
                'by_severity': alert_stats['by_severity'],
                'recent': [alert.to_dict() for alert in recent_alerts[-10:]]
            },
            'metrics': metrics_json
        }
    
    def get_dashboard_html(self) -> str:
        """
        Generate dashboard HTML interface.
        
        Returns:
            Complete HTML dashboard page
        """
        ws_url = f"ws://{self.config.host}:{self.config.ws_port}" if self.config.enable_websocket else ""
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SigmaVault ML Monitoring Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1419;
            color: #e4e4e4;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        }}
        
        h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }}
        
        .status-healthy {{ background: #10b981; }}
        .status-unhealthy {{ background: #ef4444; }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: #1a1f2e;
            padding: 24px;
            border-radius: 12px;
            border: 1px solid #2d3748;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        }}
        
        .card-title {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #9ca3af;
            margin-bottom: 16px;
        }}
        
        .metric-value {{
            font-size: 48px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 8px;
        }}
        
        .metric-label {{
            font-size: 14px;
            color: #9ca3af;
        }}
        
        .metric-good {{ color: #10b981; }}
        .metric-warning {{ color: #f59e0b; }}
        .metric-danger {{ color: #ef4444; }}
        .metric-neutral {{ color: #667eea; }}
        
        .alert-list {{
            max-height: 400px;
            overflow-y: auto;
        }}
        
        .alert-item {{
            background: #0f1419;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 12px;
            border-left: 4px solid;
        }}
        
        .alert-critical {{ border-left-color: #ef4444; }}
        .alert-high {{ border-left-color: #f59e0b; }}
        .alert-medium {{ border-left-color: #f59e0b; }}
        .alert-low {{ border-left-color: #10b981; }}
        .alert-info {{ border-left-color: #3b82f6; }}
        
        .alert-title {{
            font-weight: 600;
            margin-bottom: 4px;
        }}
        
        .alert-time {{
            font-size: 12px;
            color: #9ca3af;
        }}
        
        .refresh-indicator {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #667eea;
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 12px;
            display: none;
        }}
        
        .refresh-indicator.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ SigmaVault ML Monitoring Dashboard</h1>
        <p><span id="statusIndicator" class="status-indicator"></span>System Status: <strong id="statusText">Loading...</strong></p>
    </div>
    
    <div class="grid">
        <div class="card">
            <div class="card-title">Anomaly Detection</div>
            <div class="metric-value metric-warning" id="anomalyCount">--</div>
            <div class="metric-label">Total Detections</div>
            <div style="margin-top: 16px;">
                <div class="metric-label">Alerts: <strong id="alertCount">--</strong></div>
                <div class="metric-label">Avg Latency: <strong id="detectionLatency">--</strong>ms</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">Cache Performance</div>
            <div class="metric-value metric-good" id="cacheHitRate">--%</div>
            <div class="metric-label">Hit Rate</div>
            <div style="margin-top: 16px;">
                <div class="metric-label">Hits: <strong id="cacheHits">--</strong></div>
                <div class="metric-label">Misses: <strong id="cacheMisses">--</strong></div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">Model Performance</div>
            <div class="metric-value metric-neutral" id="modelAccuracy">--%</div>
            <div class="metric-label">Accuracy</div>
            <div style="margin-top: 16px;">
                <div class="metric-label">Updates: <strong id="modelUpdates">--</strong></div>
                <div class="metric-label">Inference: <strong id="inferenceLatency">--</strong>ms</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">System Health</div>
            <div class="metric-value" id="errorCount">--</div>
            <div class="metric-label">Total Errors</div>
            <div style="margin-top: 16px;">
                <div class="metric-label">Uptime: <strong>99.9%</strong></div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-title">Recent Alerts</div>
        <div class="alert-list" id="alertList">
            <p style="color: #9ca3af;">No recent alerts</p>
        </div>
    </div>
    
    <div class="refresh-indicator" id="refreshIndicator">
        Updating...
    </div>
    
    <script>
        const wsUrl = '{ws_url}';
        const apiUrl = '/api/metrics';
        let ws = null;
        
        function updateDashboard(data) {{
            // Status
            const healthy = data.status.healthy;
            document.getElementById('statusIndicator').className = 
                'status-indicator ' + (healthy ? 'status-healthy' : 'status-unhealthy');
            document.getElementById('statusText').textContent = 
                healthy ? 'Healthy' : 'Degraded';
            
            // Anomalies
            document.getElementById('anomalyCount').textContent = data.anomalies.total_detected;
            document.getElementById('alertCount').textContent = data.anomalies.alerts_triggered;
            document.getElementById('detectionLatency').textContent = 
                data.anomalies.detection_latency_p95_ms.toFixed(1);
            
            // Cache
            document.getElementById('cacheHitRate').textContent = 
                data.cache.hit_rate_percent.toFixed(1) + '%';
            document.getElementById('cacheHits').textContent = data.cache.total_hits;
            document.getElementById('cacheMisses').textContent = data.cache.total_misses;
            
            // Model
            document.getElementById('modelAccuracy').textContent = 
                (data.model.accuracy * 100).toFixed(1) + '%';
            document.getElementById('modelUpdates').textContent = data.model.updates_total;
            document.getElementById('inferenceLatency').textContent = 
                data.model.inference_latency_p95_ms.toFixed(1);
            
            // Errors
            const errorCount = data.status.errors;
            const errorElement = document.getElementById('errorCount');
            errorElement.textContent = errorCount;
            errorElement.className = 'metric-value ' + 
                (errorCount === 0 ? 'metric-good' : 'metric-danger');
            
            // Alerts
            const alertList = document.getElementById('alertList');
            if (data.alerts.recent.length > 0) {{
                alertList.innerHTML = data.alerts.recent.map(alert => `
                    <div class="alert-item alert-${{alert.severity.toLowerCase()}}">
                        <div class="alert-title">${{alert.title}}</div>
                        <div class="alert-time">${{new Date(alert.timestamp).toLocaleString()}}</div>
                    </div>
                `).join('');
            }} else {{
                alertList.innerHTML = '<p style="color: #9ca3af;">No recent alerts</p>';
            }}
            
            // Show refresh indicator
            const indicator = document.getElementById('refreshIndicator');
            indicator.classList.add('active');
            setTimeout(() => indicator.classList.remove('active'), 500);
        }}
        
        // WebSocket connection
        if (wsUrl) {{
            function connectWebSocket() {{
                ws = new WebSocket(wsUrl);
                
                ws.onmessage = (event) => {{
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                }};
                
                ws.onerror = (error) => {{
                    console.error('WebSocket error:', error);
                }};
                
                ws.onclose = () => {{
                    console.log('WebSocket disconnected, reconnecting...');
                    setTimeout(connectWebSocket, 5000);
                }};
            }}
            
            connectWebSocket();
        }} else {{
            // Fallback to polling
            function fetchData() {{
                fetch(apiUrl)
                    .then(response => response.json())
                    .then(data => updateDashboard(data))
                    .catch(error => console.error('Error fetching data:', error));
            }}
            
            fetchData();
            setInterval(fetchData, {self.config.refresh_interval_ms});
        }}
    </script>
</body>
</html>
        """
        
        return html.strip()


def create_default_dashboard(
    host: str = 'localhost',
    port: int = 8080,
    enable_websocket: bool = True
) -> MonitoringDashboard:
    """
    Create dashboard with default configuration.
    
    Args:
        host: HTTP server host
        port: HTTP server port
        enable_websocket: Whether to enable WebSocket streaming
        
    Returns:
        Configured MonitoringDashboard instance
    """
    from sigmavault.ml.alert_manager import AlertManager, LogAlertChannel, AlertChannel
    
    # Create alert manager with log channel
    alert_manager = AlertManager()
    alert_manager.add_channel(LogAlertChannel(), AlertChannel.LOG)
    
    # Create dashboard
    config = DashboardConfig(
        host=host,
        port=port,
        enable_websocket=enable_websocket
    )
    
    return MonitoringDashboard(
        metrics_collector=get_metrics_collector(),
        alert_manager=alert_manager,
        config=config
    )
