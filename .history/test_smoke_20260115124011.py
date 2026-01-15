"""Smoke test for monitoring components - should complete in <5 seconds."""
import sys
import signal

# Timeout handler
def timeout_handler(signum, frame):
    print("TIMEOUT - Test hung!")
    sys.exit(1)

# Set 5-second timeout on Unix-like systems
if hasattr(signal, 'SIGALRM'):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)

print("1. Testing imports...")
try:
    from sigmavault.ml.metrics_collector import MetricsCollector, MetricType
    from sigmavault.ml.alert_manager import AlertManager, AlertSeverity
    print("   [OK] Imports successful")
except Exception as e:
    print(f"   [FAIL] Import failed: {e}")
    sys.exit(1)

print("2. Testing MetricsCollector instantiation...")
try:
    collector = MetricsCollector()
    print("   [OK] MetricsCollector created")
except Exception as e:
    print(f"   [FAIL] MetricsCollector failed: {e}")
    sys.exit(1)

print("3. Testing counter...")
try:
    collector.record_counter("test", 1.0)
    print("   [OK] Counter recorded")
except Exception as e:
    print(f"   [FAIL] Counter failed: {e}")
    sys.exit(1)

print("4. Testing get_metrics...")
try:
    metrics = collector.get_metrics()
    print(f"   [OK] Got metrics: {list(metrics.keys())[:3]}...")
except Exception as e:
    print(f"   [FAIL] get_metrics failed: {e}")
    sys.exit(1)

print("5. Testing AlertManager instantiation...")
try:
    alert_mgr = AlertManager()
    print("   [OK] AlertManager created")
except Exception as e:
    print(f"   [FAIL] AlertManager failed: {e}")
    sys.exit(1)

print("\n[PASS] All smoke tests passed!")
sys.exit(0)
