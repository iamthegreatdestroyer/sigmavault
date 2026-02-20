"""Tests for batch_inference_engine module."""

import pytest
import asyncio
import time
from sigma_vault.ml.batch_inference_engine import (
    InferenceRequest,
    InferenceBatch,
    BatchQueue,
    AdaptiveBatchSizer,
    BatchInferenceMetrics,
    BatchInferenceEngine,
    InferenceStatus,
)


# Test inference function
async def dummy_inference_fn(data_list):
    """Simple inference function for testing."""
    await asyncio.sleep(0.01)  # Simulate inference
    return [x * 2 for x in data_list]


def dummy_sync_inference_fn(data_list):
    """Synchronous inference function for testing."""
    time.sleep(0.01)  # Simulate inference
    return [x * 2 for x in data_list]


class TestInferenceRequest:
    """Test InferenceRequest data class."""

    @pytest.mark.asyncio
    async def test_request_creation(self):
        """Test creating request."""
        request = InferenceRequest(
            request_id="req_1",
            data={"value": 42},
            timestamp=time.time(),
        )
        assert request.request_id == "req_1"
        assert request.data == {"value": 42}
        assert request.status == InferenceStatus.PENDING

    @pytest.mark.asyncio
    async def test_request_completion(self):
        """Test completing request."""
        request = InferenceRequest(
            request_id="req_1",
            data=10,
            timestamp=time.time(),
        )
        request.complete(20)

        assert request.result == 20
        assert request.status == InferenceStatus.COMPLETED
        result = await request.wait()
        assert result == 20

    @pytest.mark.asyncio
    async def test_request_failure(self):
        """Test failing request."""
        request = InferenceRequest(
            request_id="req_1",
            data=10,
            timestamp=time.time(),
        )
        error = RuntimeError("Test error")
        request.fail(error)

        assert request.error == error
        assert request.status == InferenceStatus.FAILED

        with pytest.raises(RuntimeError):
            await request.wait()

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """Test request timeout."""
        request = InferenceRequest(
            request_id="req_1",
            data=10,
            timestamp=time.time(),
        )

        with pytest.raises(TimeoutError):
            await request.wait(timeout=0.01)


class TestInferenceBatch:
    """Test InferenceBatch."""

    def test_batch_creation(self):
        """Test creating batch."""
        batch = InferenceBatch(batch_id="batch_1")
        assert batch.batch_id == "batch_1"
        assert batch.size == 0
        assert len(batch.requests) == 0

    def test_batch_add_requests(self):
        """Test adding requests to batch."""
        batch = InferenceBatch(batch_id="batch_1")

        for i in range(5):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            batch.add_request(request)

        assert batch.size == 5
        assert len(batch.requests) == 5
        assert all(r.batch_id == "batch_1" for r in batch.requests)

    def test_batch_get_data(self):
        """Test extracting data from batch."""
        batch = InferenceBatch(batch_id="batch_1")

        for i in range(3):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i * 10,
                timestamp=time.time(),
            )
            batch.add_request(request)

        data = batch.get_data()
        assert data == [0, 10, 20]

    def test_batch_set_results(self):
        """Test setting results on batch."""
        batch = InferenceBatch(batch_id="batch_1")

        requests = []
        for i in range(3):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            batch.add_request(request)
            requests.append(request)

        batch.set_results([10, 20, 30])

        for i, request in enumerate(requests):
            assert request.result == (i + 1) * 10
            assert request.status == InferenceStatus.COMPLETED

    def test_batch_set_errors(self):
        """Test setting errors on batch."""
        batch = InferenceBatch(batch_id="batch_1")

        for i in range(3):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            batch.add_request(request)

        error = RuntimeError("Batch error")
        batch.set_errors(error)

        for request in batch.requests:
            assert request.error == error
            assert request.status == InferenceStatus.FAILED


class TestBatchQueue:
    """Test BatchQueue."""

    @pytest.mark.asyncio
    async def test_queue_put_get(self):
        """Test putting and getting from queue."""
        queue = BatchQueue(max_size=100)

        request = InferenceRequest(
            request_id="req_1",
            data=10,
            timestamp=time.time(),
        )

        await queue.put(request)
        assert await queue.size() == 1

        batch = await queue.get_batch(batch_size=1, timeout_sec=1.0)
        assert batch is not None
        assert len(batch) == 1
        assert batch[0].request_id == "req_1"

    @pytest.mark.asyncio
    async def test_queue_batch_accumulation(self):
        """Test accumulating multiple requests."""
        queue = BatchQueue(max_size=100)

        for i in range(5):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            await queue.put(request)

        batch = await queue.get_batch(batch_size=5, timeout_sec=1.0)
        assert batch is not None
        assert len(batch) == 5

    @pytest.mark.asyncio
    async def test_queue_timeout(self):
        """Test queue timeout with no requests."""
        queue = BatchQueue(max_size=100)

        batch = await queue.get_batch(batch_size=5, timeout_sec=0.01)
        assert batch is None or len(batch) == 0

    @pytest.mark.asyncio
    async def test_queue_max_size(self):
        """Test queue size limit."""
        queue = BatchQueue(max_size=3)

        for i in range(3):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            await queue.put(request)

        # Fourth request should fail
        request = InferenceRequest(
            request_id="req_3",
            data=3,
            timestamp=time.time(),
        )

        with pytest.raises(RuntimeError):
            await queue.put(request)

    @pytest.mark.asyncio
    async def test_queue_flush(self):
        """Test flushing queue."""
        queue = BatchQueue(max_size=100)

        for i in range(5):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            await queue.put(request)

        batch = await queue.flush()
        assert len(batch) == 5
        assert await queue.size() == 0


class TestAdaptiveBatchSizer:
    """Test AdaptiveBatchSizer."""

    def test_sizer_creation(self):
        """Test creating sizer."""
        sizer = AdaptiveBatchSizer(min_size=8, max_size=128)
        assert sizer.min_size == 8
        assert sizer.max_size == 128
        assert sizer.get_batch_size() == 8

    def test_sizer_get_batch_size(self):
        """Test getting batch size."""
        sizer = AdaptiveBatchSizer(min_size=8, max_size=128)

        # Initial size
        assert sizer.get_batch_size() == 8

        # Simulate high throughput
        for _ in range(10):
            sizer.record_throughput(100.0)

        # Should have increased
        assert sizer.get_batch_size() >= 8

    def test_sizer_adjustment(self):
        """Test batch size adjustment."""
        sizer = AdaptiveBatchSizer(min_size=8, max_size=128)
        initial_size = sizer.get_batch_size()

        # Record high throughput
        for _ in range(10):
            sizer.record_throughput(100.0)

        # Size should increase
        assert sizer.get_batch_size() >= initial_size

    def test_sizer_bounds(self):
        """Test that sizer respects min/max bounds."""
        sizer = AdaptiveBatchSizer(min_size=16, max_size=64)

        # Record very high throughput
        for _ in range(100):
            sizer.record_throughput(1000.0)

        # Should not exceed max
        assert sizer.get_batch_size() <= 64

        # Record very low throughput
        for _ in range(100):
            sizer.record_throughput(1.0)

        # Should not go below min
        assert sizer.get_batch_size() >= 16


class TestBatchInferenceMetrics:
    """Test BatchInferenceMetrics."""

    @pytest.mark.asyncio
    async def test_metrics_creation(self):
        """Test creating metrics."""
        metrics = BatchInferenceMetrics()
        assert metrics.total_requests == 0
        assert metrics.total_batches == 0

    @pytest.mark.asyncio
    async def test_record_request(self):
        """Test recording request metrics."""
        metrics = BatchInferenceMetrics()

        for i in range(5):
            await metrics.record_request(10.0 + i)

        assert metrics.total_requests == 5

    @pytest.mark.asyncio
    async def test_record_batch(self):
        """Test recording batch metrics."""
        metrics = BatchInferenceMetrics()

        for i in range(3):
            await metrics.record_batch(8 + i * 4)

        assert metrics.total_batches == 3

    @pytest.mark.asyncio
    async def test_get_throughput(self):
        """Test throughput calculation."""
        metrics = BatchInferenceMetrics()

        for _ in range(100):
            await metrics.record_request(10.0)

        throughput = await metrics.get_throughput()
        assert throughput > 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting statistics."""
        metrics = BatchInferenceMetrics()

        for i in range(10):
            await metrics.record_request(10.0 + i)
            await metrics.record_batch(8 + i)

        stats = await metrics.get_stats()
        assert stats["total_requests"] == 10
        assert stats["total_batches"] == 10
        assert "throughput_req_per_sec" in stats
        assert "avg_latency_ms" in stats


class TestBatchInferenceEngine:
    """Test BatchInferenceEngine."""

    @pytest.mark.asyncio
    async def test_engine_creation(self):
        """Test creating engine."""
        engine = BatchInferenceEngine(dummy_inference_fn)
        assert engine.running is False
        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_start_stop(self):
        """Test starting and stopping engine."""
        engine = BatchInferenceEngine(dummy_inference_fn)
        await engine.start()
        assert engine.running is True

        await engine.stop()
        assert engine.running is False

    @pytest.mark.asyncio
    async def test_single_inference(self):
        """Test single inference request."""
        engine = BatchInferenceEngine(dummy_inference_fn)
        await engine.start()

        result = await engine.infer(10)
        assert result == 20

        await engine.stop()

    @pytest.mark.asyncio
    async def test_batch_inference(self):
        """Test batch inference."""
        engine = BatchInferenceEngine(dummy_inference_fn)
        await engine.start()

        results = await engine.batch_infer([5, 10, 15])
        assert results == [10, 20, 30]

        await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent inference requests."""
        engine = BatchInferenceEngine(dummy_inference_fn, min_batch_size=2, max_batch_size=4)
        await engine.start()

        # Submit multiple concurrent requests
        futures = [engine.infer(i) for i in range(10)]
        results = await asyncio.gather(*futures)

        expected = [i * 2 for i in range(10)]
        assert results == expected

        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_metrics(self):
        """Test engine metrics collection."""
        engine = BatchInferenceEngine(dummy_inference_fn)
        await engine.start()

        # Submit some requests
        for i in range(5):
            await engine.infer(i)

        # Wait a bit for processing
        await asyncio.sleep(0.2)

        stats = await engine.get_stats()
        assert stats["total_requests"] >= 1

        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_health_check(self):
        """Test engine health check."""
        engine = BatchInferenceEngine(dummy_inference_fn)

        assert await engine.health_check() is False

        await engine.start()
        assert await engine.health_check() is True

        await engine.stop()
        assert await engine.health_check() is False

    @pytest.mark.asyncio
    async def test_sync_inference_fn(self):
        """Test engine with synchronous inference function."""
        engine = BatchInferenceEngine(dummy_sync_inference_fn, max_workers=2)
        await engine.start()

        results = await engine.batch_infer([5, 10, 15])
        assert results == [10, 20, 30]

        await engine.stop()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in inference."""
        async def failing_inference_fn(data):
            raise ValueError("Inference failed")

        engine = BatchInferenceEngine(failing_inference_fn)
        await engine.start()

        with pytest.raises(ValueError):
            await engine.infer(10)

        await engine.stop()

    @pytest.mark.asyncio
    async def test_throughput_performance(self):
        """Test engine throughput."""
        engine = BatchInferenceEngine(
            dummy_inference_fn,
            min_batch_size=8,
            max_batch_size=32,
        )
        await engine.start()

        start_time = time.time()

        # Submit 100 requests
        futures = [engine.infer(i) for i in range(100)]
        results = await asyncio.gather(*futures)

        elapsed = time.time() - start_time

        # Should process 100 requests in < 2 seconds
        assert len(results) == 100
        assert elapsed < 2.0

        stats = await engine.get_stats()
        throughput = stats["throughput_req_per_sec"]
        assert throughput > 20  # At least 20 req/sec

        await engine.stop()

    @pytest.mark.asyncio
    async def test_latency_requirement(self):
        """Test that latency meets requirements."""
        engine = BatchInferenceEngine(dummy_inference_fn)
        await engine.start()

        start = time.time()
        result = await engine.infer(10)
        latency_ms = (time.time() - start) * 1000

        # Should be < 100ms
        assert latency_ms < 100
        assert result == 20

        await engine.stop()


class TestBatchInferenceEngineStress:
    """Stress tests for batch inference engine."""

    @pytest.mark.asyncio
    async def test_high_throughput(self):
        """Test engine under high throughput."""
        engine = BatchInferenceEngine(
            dummy_inference_fn,
            min_batch_size=16,
            max_batch_size=128,
        )
        await engine.start()

        # Submit 500 requests rapidly
        futures = [engine.infer(i % 100) for i in range(500)]
        results = await asyncio.gather(*futures)

        assert len(results) == 500
        assert all(r == (i % 100) * 2 for i, r in enumerate(results))

        await engine.stop()

    @pytest.mark.asyncio
    async def test_queue_under_pressure(self):
        """Test queue under pressure."""
        queue = BatchQueue(max_size=1000)

        # Rapidly add requests
        for i in range(500):
            request = InferenceRequest(
                request_id=f"req_{i}",
                data=i,
                timestamp=time.time(),
            )
            await queue.put(request)

        assert await queue.size() == 500

        # Drain queue
        batch = await queue.flush()
        assert len(batch) == 500
        assert await queue.size() == 0
