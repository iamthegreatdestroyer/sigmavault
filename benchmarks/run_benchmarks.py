#!/usr/bin/env python3
"""
ΣVAULT Benchmark Runner
=======================

Run all benchmarks and generate comprehensive performance report.

Usage:
    python run_benchmarks.py [--quick] [--category CATEGORY] [--output FILE]

Options:
    --quick         Run with fewer iterations for quick estimates
    --category      Run only specific category: crypto, scatter, filesystem
    --output        Output file for results (default: results/latest.json)

Copyright 2025 - ΣVAULT Project
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Ensure parent directory is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark_core import BenchmarkRunner, BenchmarkConfig, run_all_benchmarks


def main():
    parser = argparse.ArgumentParser(
        description="ΣVAULT Performance Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_benchmarks.py                    # Run all benchmarks
    python run_benchmarks.py --quick            # Quick estimation run
    python run_benchmarks.py --category crypto  # Only crypto benchmarks
    python run_benchmarks.py --output my_results.json
        """,
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run with fewer iterations for quick estimates",
    )
    parser.add_argument(
        "--category",
        choices=["crypto", "scatter", "filesystem", "all"],
        default="all",
        help="Run only specific benchmark category",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for results JSON",
    )
    
    args = parser.parse_args()
    
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                                                                  ║")
    print("║             ΣVAULT PERFORMANCE BENCHMARK SUITE                  ║")
    print("║                                                                  ║")
    print("║   Testing: Key Derivation • Scattering • Filesystem • I/O       ║")
    print("║                                                                  ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    
    if args.quick:
        print("⚡ Running in QUICK mode (fewer iterations)")
        print()
    
    results = {}
    runner = BenchmarkRunner()
    
    if args.category in ["all", "crypto"]:
        print("\n" + "=" * 60)
        print("📦 CRYPTOGRAPHIC BENCHMARKS")
        print("=" * 60)
        from benchmark_crypto import run_crypto_benchmarks
        crypto_results = run_crypto_benchmarks()
        results.update(crypto_results)
    
    if args.category in ["all", "scatter"]:
        print("\n" + "=" * 60)
        print("🔀 SCATTERING BENCHMARKS")
        print("=" * 60)
        from benchmark_scatter import run_scatter_benchmarks
        scatter_results = run_scatter_benchmarks()
        results.update(scatter_results)
    
    if args.category in ["all", "filesystem"]:
        print("\n" + "=" * 60)
        print("📁 FILESYSTEM BENCHMARKS")
        print("=" * 60)
        from benchmark_filesystem import run_filesystem_benchmarks
        fs_results = run_filesystem_benchmarks()
        results.update(fs_results)
    
    # Update runner with all results for summary
    runner.results = list(results.values())
    
    # Print summary
    runner.print_summary()
    
    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent / "results" / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    runner.save_results(output_path)
    
    print("\n✅ Benchmarks complete!")
    print(f"   Results saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
