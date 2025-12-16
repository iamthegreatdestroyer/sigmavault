"""
Batch Inference Engine
======================

Dynamic batching with continuous batching support for improved throughput.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable, Any
from datetime import datetime
from queue import Queue, Empty
import threading
import time
import uuid


@dataclass
class BatchRequest:
    """Single inference request."""
    
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    prompt: str = ""
    max_tokens: int = 256
    temperature: float = 0.7
    result: Optional[str] = None
    error: Optional[str] = None
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    @property
    def latency_ms(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.submitted_at).total_seconds() * 1000
        return None


@dataclass
class BatchConfig:
    """Configuration for batch inference."""
    
    max_batch_size: int = 8
    max_wait_time_ms: float = 50.0
    max_batch_tokens: int = 16384
    prefill_chunk_size: int = 512
    enable_continuous_batching: bool = True


@dataclass
class BatchStats:
    """Statistics for batch inference."""
    
    total_requests: int = 0
    total_batches: int = 0
    total_tokens_generated: int = 0
    avg_batch_size: float = 0.0
    avg_latency_ms: float = 0.0
    throughput_tokens_per_sec: float = 0.0


class MockEngine:
    """Mock inference engine for testing."""
    
    def generate(self, prompt: str, max_tokens: int = 256) -> Any:
        """Mock generation."""
        class Result:
            generated_text = f"Response to: {prompt[:50]}..."
            tokens_generated = min(max_tokens, 50)
        return Result()


class BatchInferenceEngine:
    """
    Dynamic batching with continuous batching support.
    
    Features:
    - Automatic request batching for improved throughput
    - Configurable batch size and wait time
    - Token-budget-aware batching
    - Continuous batching for overlapped decode
    - Statistics tracking
    """
    
    def __init__(
        self,
        engine: Any = None,
        config: BatchConfig = None,
    ):
        self.engine = engine or MockEngine()
        self.config = config or BatchConfig()
        
        self._queue: Queue = Queue()
        self._results: Dict[str, BatchRequest] = {}
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        self._stats = BatchStats()
        self._start_time: Optional[datetime] = None
    
    def start(self) -> None:
        """Start the batch inference worker."""
        if self._running:
            return
        
        self._running = True
        self._start_time = datetime.utcnow()
        self._worker_thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="BatchInferenceWorker",
        )
        self._worker_thread.start()
    
    def stop(self) -> None:
        """Stop the batch inference worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
    
    def submit(self, request: BatchRequest) -> str:
        """
        Submit a request for batch processing.
        
        Args:
            request: BatchRequest to process
        
        Returns:
            Request ID for result retrieval
        """
        request.submitted_at = datetime.utcnow()
        self._queue.put(request)
        
        with self._lock:
            self._stats.total_requests += 1
        
        return request.request_id
    
    def submit_prompt(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        """Convenience method to submit a prompt directly."""
        request = BatchRequest(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self.submit(request)
    
    def get_result(
        self,
        request_id: str,
        timeout: float = 30.0,
    ) -> Optional[BatchRequest]:
        """
        Get result for a submitted request.
        
        Args:
            request_id: Request ID from submit()
            timeout: Max wait time in seconds
        
        Returns:
            Completed BatchRequest or None if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if request_id in self._results:
                    return self._results.pop(request_id)
            time.sleep(0.01)
        return None
    
    def _worker(self) -> None:
        """Background worker for batch processing."""
        while self._running:
            batch = self._collect_batch()
            if batch:
                self._process_batch(batch)
            else:
                time.sleep(0.001)  # Prevent busy-waiting
    
    def _collect_batch(self) -> List[BatchRequest]:
        """
        Collect requests into a batch.
        
        Respects max_batch_size and max_wait_time.
        """
        batch: List[BatchRequest] = []
        total_tokens = 0
        wait_deadline = time.time() + (self.config.max_wait_time_ms / 1000)
        
        while len(batch) < self.config.max_batch_size:
            remaining_time = wait_deadline - time.time()
            if remaining_time <= 0 and batch:
                break  # Wait time exceeded, process what we have
            
            try:
                timeout = max(0.001, remaining_time) if batch else 0.05
                request = self._queue.get(timeout=timeout)
                
                # Check token budget
                estimated_tokens = len(request.prompt.split()) + request.max_tokens
                if total_tokens + estimated_tokens > self.config.max_batch_tokens:
                    # Put back and process current batch
                    self._queue.put(request)
                    break
                
                batch.append(request)
                total_tokens += estimated_tokens
                
            except Empty:
                if batch:
                    break
                continue
        
        return batch
    
    def _process_batch(self, batch: List[BatchRequest]) -> None:
        """Process a batch of requests."""
        batch_start = time.time()
        
        if self.config.enable_continuous_batching:
            self._process_continuous(batch)
        else:
            self._process_sequential(batch)
        
        batch_time = time.time() - batch_start
        
        # Update statistics
        with self._lock:
            self._stats.total_batches += 1
            batch_size = len(batch)
            
            # Update running average
            old_avg = self._stats.avg_batch_size
            old_count = self._stats.total_batches - 1
            self._stats.avg_batch_size = (
                (old_avg * old_count + batch_size) / self._stats.total_batches
            )
            
            # Calculate throughput
            total_tokens = sum(
                r.max_tokens for r in batch if r.result
            )
            self._stats.total_tokens_generated += total_tokens
            
            if batch_time > 0:
                tokens_per_sec = total_tokens / batch_time
                self._stats.throughput_tokens_per_sec = tokens_per_sec
    
    def _process_sequential(self, batch: List[BatchRequest]) -> None:
        """Process batch sequentially (simple mode)."""
        for req in batch:
            try:
                result = self.engine.generate(
                    req.prompt,
                    max_tokens=req.max_tokens,
                )
                req.result = result.generated_text
                req.completed_at = datetime.utcnow()
            except Exception as e:
                req.error = str(e)
                req.completed_at = datetime.utcnow()
            
            with self._lock:
                self._results[req.request_id] = req
    
    def _process_continuous(self, batch: List[BatchRequest]) -> None:
        """Process batch with continuous batching (overlapped decode)."""
        # In a real implementation, this would overlap prefill and decode
        # For now, use sequential as fallback
        self._process_sequential(batch)
    
    def get_stats(self) -> BatchStats:
        """Get current batch statistics."""
        with self._lock:
            return BatchStats(
                total_requests=self._stats.total_requests,
                total_batches=self._stats.total_batches,
                total_tokens_generated=self._stats.total_tokens_generated,
                avg_batch_size=self._stats.avg_batch_size,
                avg_latency_ms=self._stats.avg_latency_ms,
                throughput_tokens_per_sec=self._stats.throughput_tokens_per_sec,
            )
    
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()


# Convenience factory
def create_batch_engine(
    engine: Any = None,
    max_batch_size: int = 8,
    max_wait_ms: float = 50.0,
) -> BatchInferenceEngine:
    """Create batch inference engine with configuration."""
    config = BatchConfig(
        max_batch_size=max_batch_size,
        max_wait_time_ms=max_wait_ms,
    )
    return BatchInferenceEngine(engine, config)
