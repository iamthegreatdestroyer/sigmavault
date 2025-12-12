"""
ΣVAULT Benchmark Core Framework
===============================

Core infrastructure for running and collecting benchmark results.
Provides timing utilities, memory tracking, and result aggregation.

Copyright 2025 - ΣVAULT Project
"""

import time
import statistics
import gc
import sys
import tracemalloc
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional, Tuple
from pathlib import Path
from functools import wraps
import json
from datetime import datetime


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    warmup_iterations: int = 3
    min_iterations: int = 5
    max_iterations: int = 100
    target_time_seconds: float = 5.0  # Run for at least this long
    gc_collect_between: bool = True
    track_memory: bool = True
    
    # File size presets
    SMALL_FILE: int = 1024          # 1 KB
    MEDIUM_FILE: int = 1024 * 1024  # 1 MB
    LARGE_FILE: int = 100 * 1024 * 1024  # 100 MB


@dataclass
class BenchmarkResult:
    """Results from a single benchmark."""
    name: str
    iterations: int
    total_time_seconds: float
    mean_time_ms: float
    median_time_ms: float
    std_dev_ms: float
    min_time_ms: float
    max_time_ms: float
    throughput: Optional[float] = None  # bytes/sec for IO operations
    throughput_unit: str = "ops/sec"
    memory_peak_mb: Optional[float] = None
    memory_delta_mb: Optional[float] = None
    data_size_bytes: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        lines = [
            f"╔══════════════════════════════════════════════════════════════════╗",
            f"║ Benchmark: {self.name:<54}║",
            f"╠══════════════════════════════════════════════════════════════════╣",
            f"║  Iterations: {self.iterations:<8} Total Time: {self.total_time_seconds:>10.3f}s           ║",
            f"║  Mean:       {self.mean_time_ms:>10.3f} ms                                    ║",
            f"║  Median:     {self.median_time_ms:>10.3f} ms                                    ║",
            f"║  Std Dev:    {self.std_dev_ms:>10.3f} ms                                    ║",
            f"║  Min:        {self.min_time_ms:>10.3f} ms                                    ║",
            f"║  Max:        {self.max_time_ms:>10.3f} ms                                    ║",
        ]
        
        if self.throughput:
            lines.append(
                f"║  Throughput: {self.throughput:>10.2f} {self.throughput_unit:<27}║"
            )
        
        if self.memory_peak_mb:
            lines.append(
                f"║  Memory Peak: {self.memory_peak_mb:>9.2f} MB                                  ║"
            )
        
        if self.memory_delta_mb:
            lines.append(
                f"║  Memory Δ:    {self.memory_delta_mb:>9.2f} MB                                  ║"
            )
        
        lines.append(
            f"╚══════════════════════════════════════════════════════════════════╝"
        )
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_seconds": self.total_time_seconds,
            "mean_time_ms": self.mean_time_ms,
            "median_time_ms": self.median_time_ms,
            "std_dev_ms": self.std_dev_ms,
            "min_time_ms": self.min_time_ms,
            "max_time_ms": self.max_time_ms,
            "throughput": self.throughput,
            "throughput_unit": self.throughput_unit,
            "memory_peak_mb": self.memory_peak_mb,
            "memory_delta_mb": self.memory_delta_mb,
            "data_size_bytes": self.data_size_bytes,
            "metadata": self.metadata,
        }


class BenchmarkRunner:
    """
    Core benchmark runner with timing and memory tracking.
    
    Usage:
        runner = BenchmarkRunner(config)
        result = runner.run(my_function, "test_name", data_size=1024)
    """
    
    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()
        self.results: List[BenchmarkResult] = []
    
    def run(
        self,
        func: Callable[[], Any],
        name: str,
        data_size: Optional[int] = None,
        setup: Optional[Callable[[], None]] = None,
        teardown: Optional[Callable[[], None]] = None,
    ) -> BenchmarkResult:
        """
        Run a benchmark.
        
        Args:
            func: The function to benchmark (no arguments)
            name: Name for this benchmark
            data_size: Size of data being processed (for throughput calc)
            setup: Optional setup function called before each iteration
            teardown: Optional teardown function called after each iteration
            
        Returns:
            BenchmarkResult with timing and memory statistics
        """
        times_ms: List[float] = []
        memory_peak = 0.0
        memory_start = 0.0
        
        # Warmup phase
        for _ in range(self.config.warmup_iterations):
            if setup:
                setup()
            func()
            if teardown:
                teardown()
        
        # Main benchmark loop
        iteration = 0
        start_total = time.perf_counter()
        
        # Start memory tracking
        if self.config.track_memory:
            tracemalloc.start()
            memory_start = tracemalloc.get_traced_memory()[0] / (1024 * 1024)
        
        while True:
            if self.config.gc_collect_between:
                gc.collect()
            
            if setup:
                setup()
            
            # Time the function
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            
            if teardown:
                teardown()
            
            times_ms.append((end - start) * 1000)  # Convert to ms
            iteration += 1
            
            # Track memory
            if self.config.track_memory:
                current_mem = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
                memory_peak = max(memory_peak, current_mem)
            
            total_elapsed = time.perf_counter() - start_total
            
            # Check termination conditions
            if iteration >= self.config.max_iterations:
                break
            if (iteration >= self.config.min_iterations and 
                total_elapsed >= self.config.target_time_seconds):
                break
        
        # Stop memory tracking
        if self.config.track_memory:
            tracemalloc.stop()
        
        total_time = time.perf_counter() - start_total
        
        # Calculate statistics
        mean_time = statistics.mean(times_ms)
        median_time = statistics.median(times_ms)
        std_dev = statistics.stdev(times_ms) if len(times_ms) > 1 else 0.0
        min_time = min(times_ms)
        max_time = max(times_ms)
        
        # Calculate throughput
        throughput = None
        throughput_unit = "ops/sec"
        if data_size:
            ops_per_sec = 1000 / mean_time
            bytes_per_sec = data_size * ops_per_sec
            if bytes_per_sec >= 1024 * 1024 * 1024:
                throughput = bytes_per_sec / (1024 * 1024 * 1024)
                throughput_unit = "GB/sec"
            elif bytes_per_sec >= 1024 * 1024:
                throughput = bytes_per_sec / (1024 * 1024)
                throughput_unit = "MB/sec"
            elif bytes_per_sec >= 1024:
                throughput = bytes_per_sec / 1024
                throughput_unit = "KB/sec"
            else:
                throughput = bytes_per_sec
                throughput_unit = "B/sec"
        
        result = BenchmarkResult(
            name=name,
            iterations=iteration,
            total_time_seconds=total_time,
            mean_time_ms=mean_time,
            median_time_ms=median_time,
            std_dev_ms=std_dev,
            min_time_ms=min_time,
            max_time_ms=max_time,
            throughput=throughput,
            throughput_unit=throughput_unit,
            memory_peak_mb=memory_peak if self.config.track_memory else None,
            memory_delta_mb=(memory_peak - memory_start) if self.config.track_memory else None,
            data_size_bytes=data_size,
        )
        
        self.results.append(result)
        return result
    
    def run_suite(
        self,
        benchmarks: List[Tuple[str, Callable[[], Any], Optional[int]]],
    ) -> List[BenchmarkResult]:
        """
        Run a suite of benchmarks.
        
        Args:
            benchmarks: List of (name, func, data_size) tuples
            
        Returns:
            List of BenchmarkResult
        """
        results = []
        for name, func, data_size in benchmarks:
            print(f"\n🔄 Running benchmark: {name}...")
            result = self.run(func, name, data_size)
            print(result)
            results.append(result)
        return results
    
    def save_results(self, filepath: Path) -> None:
        """Save benchmark results to JSON file."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "platform": sys.platform,
            "results": [r.to_dict() for r in self.results],
        }
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n📊 Results saved to: {filepath}")
    
    def print_summary(self) -> None:
        """Print a summary table of all results."""
        print("\n" + "=" * 70)
        print("                     BENCHMARK SUMMARY")
        print("=" * 70)
        print(f"{'Benchmark':<40} {'Mean (ms)':>12} {'Throughput':>15}")
        print("-" * 70)
        
        for result in self.results:
            throughput_str = ""
            if result.throughput:
                throughput_str = f"{result.throughput:.2f} {result.throughput_unit}"
            print(f"{result.name:<40} {result.mean_time_ms:>12.3f} {throughput_str:>15}")
        
        print("=" * 70)


def benchmark(
    name: str = None,
    data_size: int = None,
    iterations: int = None,
):
    """
    Decorator for benchmarking functions.
    
    Usage:
        @benchmark(name="my_test", data_size=1024)
        def test_function():
            # code to benchmark
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal name
            if name is None:
                name = func.__name__
            
            config = BenchmarkConfig()
            if iterations:
                config.min_iterations = iterations
                config.max_iterations = iterations
            
            runner = BenchmarkRunner(config)
            result = runner.run(lambda: func(*args, **kwargs), name, data_size)
            return result
        return wrapper
    return decorator


def run_all_benchmarks() -> Dict[str, BenchmarkResult]:
    """
    Run the complete benchmark suite.
    
    Returns:
        Dictionary mapping benchmark names to results
    """
    from .benchmark_crypto import run_crypto_benchmarks
    from .benchmark_scatter import run_scatter_benchmarks
    from .benchmark_filesystem import run_filesystem_benchmarks
    
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║          ΣVAULT COMPREHENSIVE BENCHMARK SUITE                   ║")
    print("║                                                                  ║")
    print("║  Testing: Key Derivation, Scattering, Mixing, Filesystem        ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    
    results = {}
    
    # Run each benchmark category
    print("\n\n📦 CRYPTOGRAPHIC BENCHMARKS")
    print("━" * 50)
    crypto_results = run_crypto_benchmarks()
    results.update(crypto_results)
    
    print("\n\n🔀 SCATTERING BENCHMARKS")
    print("━" * 50)
    scatter_results = run_scatter_benchmarks()
    results.update(scatter_results)
    
    print("\n\n📁 FILESYSTEM BENCHMARKS")
    print("━" * 50)
    fs_results = run_filesystem_benchmarks()
    results.update(fs_results)
    
    # Save results
    runner = BenchmarkRunner()
    runner.results = list(results.values())
    runner.save_results(Path(__file__).parent / "results" / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    runner.print_summary()
    
    return results
