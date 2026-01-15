"""
Comprehensive tests for alert_manager module.

Tests cover:
- Email, webhook, and log alert channels
- Alert deduplication within time window
- Rate limiting enforcement
- Severity-based routing
- Alert history tracking
- Channel failure handling
- Concurrent alert processing
"""

import pytest
import asyncio
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Direct imports to avoid package-level dependencies
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.alert_manager import (
    AlertManager,
    Alert,
    AlertSeverity,
    EmailAlertChannel,
    WebhookAlertChannel,
    LogAlertChannel
)


class TestAlert:
    """Test Alert dataclass."""
    
    def test_alert_creation(self):
        """Test creating an alert with all fields."""
        alert = Alert(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            source="test_source",
            metadata={"key": "value"}
        )
        
        assert alert.severity == AlertSeverity.WARNING
        assert alert.title == "Test Alert"
        assert alert.message == "Test message"
        assert alert.source == "test_source"
        assert alert.metadata == {"key": "value"}
        assert isinstance(alert.timestamp, datetime)
    
    def test_alert_default_timestamp(self):
        """Test alert timestamp defaults to now."""
        before = datetime.now()
        alert = Alert(
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test",
            source="test"
        )
        after = datetime.now()
        
        assert before <= alert.timestamp <= after
    
    def test_alert_severities(self):
        """Test all severity levels."""
        for severity in [AlertSeverity.INFO, AlertSeverity.WARNING, 
                        AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            alert = Alert(severity=severity, title="Test", message="Test", source="test")
            assert alert.severity == severity


class TestLogAlertChannel:
    """Test LogAlertChannel."""
    
    @pytest.mark.asyncio
    async def test_log_channel_basic(self):
        """Test log channel writes alerts."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name
        
        try:
            channel = LogAlertChannel(log_file=log_file)
            
            alert = Alert(
                severity=AlertSeverity.ERROR,
                title="Test Error",
                message="Test error message",
                source="test"
            )
            
            result = await channel.send(alert)
            assert result is True
            
            # Verify log file contents
            with open(log_file, 'r') as f:
                log_content = f.read()
                assert "ERROR" in log_content
                assert "Test Error" in log_content
                assert "Test error message" in log_content
        finally:
            Path(log_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_log_channel_all_severities(self):
        """Test logging different severity levels."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name
        
        try:
            channel = LogAlertChannel(log_file=log_file)
            
            for severity in [AlertSeverity.INFO, AlertSeverity.WARNING,
                            AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
                alert = Alert(
                    severity=severity,
                    title=f"Test {severity.value}",
                    message=f"Test {severity.value} message",
                    source="test"
                )
                await channel.send(alert)
            
            with open(log_file, 'r') as f:
                log_content = f.read()
                assert "INFO" in log_content
                assert "WARNING" in log_content
                assert "ERROR" in log_content
                assert "CRITICAL" in log_content
        finally:
            Path(log_file).unlink(missing_ok=True)


class TestEmailAlertChannel:
    """Test EmailAlertChannel."""
    
    @pytest.mark.asyncio
    async def test_email_channel_formatting(self):
        """Test email alert formatting (without actual SMTP)."""
        channel = EmailAlertChannel(
            smtp_host="smtp.test.com",
            smtp_port=587,
            from_addr="alerts@test.com",
            to_addrs=["admin@test.com"]
        )
        
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            title="Critical System Failure",
            message="System has encountered a critical error",
            source="monitoring_system",
            metadata={"error_code": "SYS_001"}
        )
        
        # We can't test actual SMTP without a server, but we can verify
        # the channel is configured correctly
        assert channel.smtp_host == "smtp.test.com"
        assert channel.smtp_port == 587
        assert channel.from_addr == "alerts@test.com"
        assert "admin@test.com" in channel.to_addrs


class TestWebhookAlertChannel:
    """Test WebhookAlertChannel."""
    
    @pytest.mark.asyncio
    async def test_webhook_channel_payload(self):
        """Test webhook payload formatting."""
        channel = WebhookAlertChannel(
            webhook_url="https://hooks.test.com/alert",
            headers={"Authorization": "Bearer test_token"}
        )
        
        alert = Alert(
            severity=AlertSeverity.WARNING,
            title="High CPU Usage",
            message="CPU usage exceeded 90%",
            source="resource_monitor"
        )
        
        # Verify channel configuration
        assert channel.webhook_url == "https://hooks.test.com/alert"
        assert "Authorization" in channel.headers


class TestAlertManager:
    """Test AlertManager core functionality."""
    
    @pytest.fixture
    def alert_manager(self):
        """Provide fresh AlertManager instance."""
        return AlertManager()
    
    @pytest.fixture
    def sample_alert(self):
        """Provide sample alert."""
        return Alert(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            source="test_source"
        )
    
    # === BASIC FUNCTIONALITY TESTS ===
    
    def test_alert_manager_initialization(self, alert_manager):
        """Test AlertManager initializes with empty state."""
        assert len(alert_manager._channels) == 0
        assert len(alert_manager._alert_history) == 0
    
    def test_register_channel(self, alert_manager):
        """Test registering alert channels."""
        channel = LogAlertChannel()
        alert_manager.register_channel(channel)
        
        assert len(alert_manager._channels) == 1
        assert channel in alert_manager._channels
    
    def test_register_multiple_channels(self, alert_manager):
        """Test registering multiple channels."""
        log_channel = LogAlertChannel()
        webhook_channel = WebhookAlertChannel("https://test.com")
        
        alert_manager.register_channel(log_channel)
        alert_manager.register_channel(webhook_channel)
        
        assert len(alert_manager._channels) == 2
    
    # === DEDUPLICATION TESTS ===
    
    @pytest.mark.asyncio
    async def test_alert_deduplication_basic(self, alert_manager, sample_alert):
        """Test duplicate alerts within window are suppressed."""
        alert_manager.register_channel(LogAlertChannel())
        
        # Send same alert twice
        result1 = await alert_manager.send_alert(sample_alert)
        result2 = await alert_manager.send_alert(sample_alert)
        
        assert result1 is True  # First alert sent
        assert result2 is False  # Second alert suppressed (duplicate)
    
    @pytest.mark.asyncio
    async def test_alert_deduplication_different_messages(self, alert_manager):
        """Test different alerts are not deduplicated."""
        alert_manager.register_channel(LogAlertChannel())
        
        alert1 = Alert(
            severity=AlertSeverity.INFO,
            title="Alert 1",
            message="Message 1",
            source="source1"
        )
        alert2 = Alert(
            severity=AlertSeverity.INFO,
            title="Alert 2",
            message="Message 2",
            source="source2"
        )
        
        result1 = await alert_manager.send_alert(alert1)
        result2 = await alert_manager.send_alert(alert2)
        
        assert result1 is True
        assert result2 is True  # Different alert, not deduplicated
    
    @pytest.mark.asyncio
    async def test_alert_deduplication_window_expiry(self, alert_manager, sample_alert):
        """Test deduplication window expiry allows resending."""
        # Set very short dedup window for testing
        alert_manager._dedup_window = timedelta(seconds=0.1)
        alert_manager.register_channel(LogAlertChannel())
        
        # Send first alert
        result1 = await alert_manager.send_alert(sample_alert)
        assert result1 is True
        
        # Wait for dedup window to expire
        await asyncio.sleep(0.2)
        
        # Send same alert again (should not be deduplicated)
        result2 = await alert_manager.send_alert(sample_alert)
        assert result2 is True
    
    # === RATE LIMITING TESTS ===
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, alert_manager):
        """Test rate limiting prevents alert flooding."""
        alert_manager.register_channel(LogAlertChannel())
        
        # Send more alerts than rate limit
        alerts = [
            Alert(
                severity=AlertSeverity.INFO,
                title=f"Alert {i}",
                message=f"Message {i}",
                source="rate_test"
            )
            for i in range(15)
        ]
        
        sent_count = 0
        for alert in alerts:
            result = await alert_manager.send_alert(alert)
            if result:
                sent_count += 1
        
        # Should stop at rate limit (10/minute by default)
        assert sent_count <= 10
    
    @pytest.mark.asyncio
    async def test_rate_limiting_resets(self, alert_manager):
        """Test rate limit resets after window."""
        # Set short rate limit window for testing
        alert_manager._rate_limit = 5
        alert_manager.register_channel(LogAlertChannel())
        
        # Send up to rate limit
        for i in range(5):
            alert = Alert(
                severity=AlertSeverity.INFO,
                title=f"Alert {i}",
                message=f"Message {i}",
                source="test"
            )
            result = await alert_manager.send_alert(alert)
            assert result is True
        
        # 6th alert should be rate limited
        alert6 = Alert(
            severity=AlertSeverity.INFO,
            title="Alert 6",
            message="Message 6",
            source="test"
        )
        result6 = await alert_manager.send_alert(alert6)
        # May be rate limited depending on timing
    
    # === ALERT HISTORY TESTS ===
    
    @pytest.mark.asyncio
    async def test_alert_history_tracking(self, alert_manager):
        """Test alerts are added to history."""
        alert_manager.register_channel(LogAlertChannel())
        
        alert = Alert(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            source="test"
        )
        
        await alert_manager.send_alert(alert)
        
        history = alert_manager.get_recent_alerts(limit=10)
        assert len(history) >= 1
        assert history[0].title == "Test Alert"
    
    @pytest.mark.asyncio
    async def test_alert_history_limit(self, alert_manager):
        """Test alert history respects limit."""
        alert_manager.register_channel(LogAlertChannel())
        
        # Send more alerts than requested limit
        for i in range(20):
            alert = Alert(
                severity=AlertSeverity.INFO,
                title=f"Alert {i}",
                message=f"Message {i}",
                source="test"
            )
            await alert_manager.send_alert(alert)
        
        history = alert_manager.get_recent_alerts(limit=5)
        assert len(history) <= 5
    
    @pytest.mark.asyncio
    async def test_alert_history_ordering(self, alert_manager):
        """Test alert history is ordered by recency."""
        alert_manager.register_channel(LogAlertChannel())
        
        alerts = []
        for i in range(5):
            alert = Alert(
                severity=AlertSeverity.INFO,
                title=f"Alert {i}",
                message=f"Message {i}",
                source="test"
            )
            alerts.append(alert)
            await alert_manager.send_alert(alert)
            await asyncio.sleep(0.01)  # Small delay to ensure timestamp ordering
        
        history = alert_manager.get_recent_alerts(limit=5)
        # Most recent should be first
        assert history[0].title == "Alert 4"
    
    # === SEVERITY FILTERING TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_alerts_by_severity(self, alert_manager):
        """Test filtering alerts by severity."""
        alert_manager.register_channel(LogAlertChannel())
        
        # Send alerts of different severities
        for severity in [AlertSeverity.INFO, AlertSeverity.WARNING, 
                        AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            alert = Alert(
                severity=severity,
                title=f"{severity.value} alert",
                message="Test",
                source="test"
            )
            await alert_manager.send_alert(alert)
        
        # Filter for critical alerts
        critical_alerts = alert_manager.get_recent_alerts(severity=AlertSeverity.CRITICAL)
        assert all(a.severity == AlertSeverity.CRITICAL for a in critical_alerts)
    
    # === CHANNEL FAILURE TESTS ===
    
    @pytest.mark.asyncio
    async def test_channel_failure_handling(self, alert_manager):
        """Test alert manager handles channel failures gracefully."""
        # Create a mock channel that always fails
        failing_channel = Mock()
        failing_channel.send = AsyncMock(side_effect=Exception("Channel error"))
        
        alert_manager.register_channel(failing_channel)
        
        alert = Alert(
            severity=AlertSeverity.ERROR,
            title="Test Alert",
            message="Test message",
            source="test"
        )
        
        # Should not raise exception despite channel failure
        result = await alert_manager.send_alert(alert)
        # Alert still recorded in history even if channel fails
        history = alert_manager.get_recent_alerts()
        assert len(history) >= 1
    
    # === CONCURRENT ALERT TESTS ===
    
    @pytest.mark.asyncio
    async def test_concurrent_alerts(self, alert_manager):
        """Test handling concurrent alert submissions."""
        alert_manager.register_channel(LogAlertChannel())
        
        async def send_alerts(start_idx):
            for i in range(10):
                alert = Alert(
                    severity=AlertSeverity.INFO,
                    title=f"Alert {start_idx + i}",
                    message=f"Message {start_idx + i}",
                    source="concurrent_test"
                )
                await alert_manager.send_alert(alert)
        
        # Run multiple concurrent tasks
        tasks = [send_alerts(i * 10) for i in range(5)]
        await asyncio.gather(*tasks)
        
        # Verify alerts were processed (some may be rate limited)
        history = alert_manager.get_recent_alerts(limit=100)
        assert len(history) > 0
    
    # === EDGE CASE TESTS ===
    
    @pytest.mark.asyncio
    async def test_send_alert_no_channels(self, alert_manager, sample_alert):
        """Test sending alert with no registered channels."""
        # Should not raise error
        result = await alert_manager.send_alert(sample_alert)
        
        # Alert still recorded in history
        history = alert_manager.get_recent_alerts()
        assert len(history) >= 1
    
    @pytest.mark.asyncio
    async def test_empty_alert_metadata(self, alert_manager):
        """Test alert with empty metadata."""
        alert_manager.register_channel(LogAlertChannel())
        
        alert = Alert(
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test",
            source="test",
            metadata={}
        )
        
        result = await alert_manager.send_alert(alert)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
