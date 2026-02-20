"""
Real-time Monitoring Dashboard for ΣVAULT ML Integration.

Provides WebSocket-based real-time streaming of ML metrics, anomaly events,
and system health indicators to connected clients. Supports multiple concurrent
dashboards with adaptive broadcast patterns.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable
from collections import deque
from dataclasses import dataclass, asdict
import logging

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Point-in-time snapshot of system metrics."""
    timestamp: float
    anomaly_count: int
    model_latency_ms: float
    cache_hit_rate: float
    active_connections: int
    predictions_per_sec: float
    memory_usage_mb: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class AnomalyEvent:
    """Detected anomaly event for dashboard display."""
    timestamp: float
    file_id: str
    anomaly_type: str
    confidence: float
    severity: str  # 'low', 'medium', 'high', 'critical'
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


class MetricsBuffer:
    """Circular buffer for recent metrics snapshots."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.buffer: deque = deque(maxlen=capacity)
        self.lock = asyncio.Lock()

    async def add(self, snapshot: MetricSnapshot) -> None:
        """Add metric snapshot to buffer."""
        async with self.lock:
            self.buffer.append(snapshot)

    async def get_recent(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get most recent N snapshots."""
        async with self.lock:
            recent = list(self.buffer)[-count:]
            return [s.to_dict() for s in recent]

    async def get_time_range(self, start_ts: float, end_ts: float) -> List[Dict[str, Any]]:
        """Get snapshots within timestamp range."""
        async with self.lock:
            filtered = [
                s for s in self.buffer
                if start_ts <= s.timestamp <= end_ts
            ]
            return [s.to_dict() for s in filtered]


class AnomalyEventBuffer:
    """Circular buffer for recent anomaly events."""

    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.buffer: deque = deque(maxlen=capacity)
        self.lock = asyncio.Lock()

    async def add(self, event: AnomalyEvent) -> None:
        """Add anomaly event to buffer."""
        async with self.lock:
            self.buffer.append(event)

    async def get_recent(self, count: int = 50) -> List[Dict[str, Any]]:
        """Get most recent N events."""
        async with self.lock:
            recent = list(self.buffer)[-count:]
            return [e.to_dict() for e in recent]

    async def get_by_severity(self, severity: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent events of specific severity."""
        async with self.lock:
            filtered = [
                e for e in self.buffer
                if e.severity == severity
            ][-count:]
            return [e.to_dict() for e in filtered]


class MonitoringDashboard:
    """
    Real-time monitoring dashboard using WebSocket for streaming updates.

    Manages client connections, broadcasts metrics, handles subscription patterns,
    and provides multi-view capability for different monitoring perspectives.
    """

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.running = False
        self.server = None

        # Connection management
        self.clients: Set[WebSocketServerProtocol] = set()
        self.subscriptions: Dict[str, Set[WebSocketServerProtocol]] = {
            'metrics': set(),
            'anomalies': set(),
            'performance': set(),
            'all': set(),
        }

        # Buffers
        self.metrics_buffer = MetricsBuffer(capacity=1000)
        self.anomaly_buffer = AnomalyEventBuffer(capacity=500)

        # Broadcast settings
        self.broadcast_interval_metrics = 1.0  # seconds
        self.broadcast_interval_anomalies = 0.5  # seconds
        self.max_latency = 100  # ms

    async def start(self) -> None:
        """Start WebSocket server."""
        if WEBSOCKETS_AVAILABLE:
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
            )
            self.running = True
            logger.info(f"Dashboard started on ws://{self.host}:{self.port}")
        else:
            logger.warning("websockets library not available, dashboard disabled")

    async def stop(self) -> None:
        """Stop WebSocket server."""
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all client connections
        for client in list(self.clients):
            await client.close()

        logger.info("Dashboard stopped")

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle new client connection."""
        self.clients.add(websocket)
        subscription = 'all'
        self.subscriptions['all'].add(websocket)

        try:
            logger.info(f"New client connected from {websocket.remote_address}")

            # Send initial state
            await self._send_initial_state(websocket)

            # Handle incoming messages
            async for message in websocket:
                await self._handle_message(websocket, message, subscription)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            # Cleanup
            self.clients.discard(websocket)
            for subs_set in self.subscriptions.values():
                subs_set.discard(websocket)

    async def _send_initial_state(self, websocket: WebSocketServerProtocol) -> None:
        """Send initial state to new client."""
        recent_metrics = await self.metrics_buffer.get_recent(100)
        recent_anomalies = await self.anomaly_buffer.get_recent(50)

        message = {
            'type': 'initial_state',
            'timestamp': time.time(),
            'metrics': recent_metrics,
            'anomalies': recent_anomalies,
            'active_connections': len(self.clients),
        }

        await websocket.send(json.dumps(message))

    async def _handle_message(
        self,
        websocket: WebSocketServerProtocol,
        message: str,
        subscription: str
    ) -> None:
        """Handle incoming client message."""
        try:
            data = json.loads(message)
            cmd = data.get('command')

            if cmd == 'subscribe':
                new_sub = data.get('subscription', 'all')
                if new_sub in self.subscriptions:
                    # Remove from old subscription
                    self.subscriptions[subscription].discard(websocket)
                    # Add to new subscription
                    self.subscriptions[new_sub].add(websocket)
                    await websocket.send(json.dumps({
                        'type': 'subscription_changed',
                        'subscription': new_sub,
                    }))

            elif cmd == 'get_metrics':
                metrics = await self.metrics_buffer.get_recent(data.get('count', 50))
                await websocket.send(json.dumps({
                    'type': 'metrics_response',
                    'metrics': metrics,
                }))

            elif cmd == 'get_anomalies':
                anomalies = await self.anomaly_buffer.get_recent(data.get('count', 20))
                await websocket.send(json.dumps({
                    'type': 'anomalies_response',
                    'anomalies': anomalies,
                }))

        except json.JSONDecodeError:
            logger.error("Invalid JSON message")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def broadcast_metrics(self, snapshot: MetricSnapshot) -> None:
        """Broadcast metrics to subscribed clients."""
        if not self.clients:
            return

        message = json.dumps({
            'type': 'metrics_update',
            'timestamp': snapshot.timestamp,
            'data': snapshot.to_dict(),
        })

        # Add to buffer for new clients
        await self.metrics_buffer.add(snapshot)

        # Send to subscribed clients
        clients_to_notify = (
            self.subscriptions['metrics'] |
            self.subscriptions['all']
        )

        disconnected = set()
        for client in clients_to_notify:
            try:
                await asyncio.wait_for(
                    client.send(message),
                    timeout=self.max_latency / 1000.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Client send timeout: {client.remote_address}")
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

        # Cleanup disconnected clients
        for client in disconnected:
            self.clients.discard(client)

    async def broadcast_anomaly(self, event: AnomalyEvent) -> None:
        """Broadcast anomaly event to subscribed clients."""
        if not self.clients:
            return

        message = json.dumps({
            'type': 'anomaly_event',
            'timestamp': event.timestamp,
            'data': event.to_dict(),
        })

        # Add to buffer
        await self.anomaly_buffer.add(event)

        # Send to subscribed clients
        clients_to_notify = (
            self.subscriptions['anomalies'] |
            self.subscriptions['all']
        )

        disconnected = set()
        for client in clients_to_notify:
            try:
                await asyncio.wait_for(
                    client.send(message),
                    timeout=self.max_latency / 1000.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Client send timeout: {client.remote_address}")
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

        # Cleanup disconnected clients
        for client in disconnected:
            self.clients.discard(client)

    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get current dashboard summary."""
        recent_metrics = await self.metrics_buffer.get_recent(1)
        recent_anomalies = await self.anomaly_buffer.get_recent(10)
        high_severity = await self.anomaly_buffer.get_by_severity('critical', 10)

        current_metric = recent_metrics[0] if recent_metrics else None

        return {
            'timestamp': time.time(),
            'active_connections': len(self.clients),
            'current_metrics': current_metric,
            'recent_anomalies': recent_anomalies,
            'critical_anomalies': high_severity,
            'metrics_buffer_size': len(self.metrics_buffer.buffer),
            'anomaly_buffer_size': len(self.anomaly_buffer.buffer),
        }


# Global dashboard instance
_dashboard: Optional[MonitoringDashboard] = None


def get_dashboard(host: str = "localhost", port: int = 8765) -> MonitoringDashboard:
    """Get or create global dashboard instance."""
    global _dashboard
    if _dashboard is None:
        _dashboard = MonitoringDashboard(host, port)
    return _dashboard


async def broadcast_metrics(snapshot: MetricSnapshot) -> None:
    """Helper to broadcast metrics to dashboard."""
    dashboard = get_dashboard()
    if dashboard.running:
        await dashboard.broadcast_metrics(snapshot)


async def broadcast_anomaly(event: AnomalyEvent) -> None:
    """Helper to broadcast anomaly event to dashboard."""
    dashboard = get_dashboard()
    if dashboard.running:
        await dashboard.broadcast_anomaly(event)
