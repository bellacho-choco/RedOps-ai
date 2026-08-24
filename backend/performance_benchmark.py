"""
====================================================================
PROJECT REDOPS-AI - PERFORMANCE BENCHMARKING SUITE
Comprehensive performance testing and benchmarking framework
====================================================================
"""

import asyncio
import time
import statistics
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import threading
from functools import wraps


class BenchmarkCategory(Enum):
    GRAPH_OPERATIONS = "graph_operations"
    HTTP_REQUESTS = "http_requests"
    PARALLEL_PROCESSING = "parallel_processing"
    MEMORY_OPERATIONS = "memory_operations"
    COMPUTE_INTENSIVE = "compute_intensive"


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    category: BenchmarkCategory
    duration_ms: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class BenchmarkSummary:
    """Statistical summary of benchmark results."""
    name: str
    category: BenchmarkCategory
    total_runs: int
    successful_runs: int
    failed_runs: int
    min_ms: float
    max_ms: float
    avg_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    throughput: Optional[float] = None  # operations per second
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "avg_ms": self.avg_ms,
            "median_ms": self.median_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "std_dev_ms": self.std_dev_ms,
            "throughput": self.throughput
        }


class Benchmark:
    """
    Represents a single benchmark test case.
    """
    def __init__(self, 
                 name: str,
                 category: BenchmarkCategory,
                 func: Callable,
                 warmup_runs: int = 3,
                 benchmark_runs: int = 10,
                 timeout: float = 30.0):
        self.name = name
        self.category = category
        self.func = func
        self.warmup_runs = warmup_runs
        self.benchmark_runs = benchmark_runs
        self.timeout = timeout
        self.results: List[BenchmarkResult] = []
    
    async def run(self) -> BenchmarkSummary:
        """Run the benchmark and return summary statistics."""
        self.results = []
        
        # Warmup runs (not included in statistics)
        for _ in range(self.warmup_runs):
            try:
                if asyncio.iscoroutinefunction(self.func):
                    await asyncio.wait_for(self.func(), timeout=self.timeout)
                else:
                    self.func()
            except Exception:
                pass  # Ignore warmup errors
        
        # Benchmark runs
        successful_durations = []
        failed_runs = 0
        
        for i in range(self.benchmark_runs):
            start_time = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(self.func):
                    await asyncio.wait_for(self.func(), timeout=self.timeout)
                else:
                    self.func()
                
                duration_ms = (time.perf_counter() - start_time) * 1000
                successful_durations.append(duration_ms)
                
                self.results.append(BenchmarkResult(
                    name=self.name,
                    category=self.category,
                    duration_ms=duration_ms,
                    success=True
                ))
                
            except Exception as e:
                failed_runs += 1
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                self.results.append(BenchmarkResult(
                    name=self.name,
                    category=self.category,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(e)
                ))
        
        # Calculate statistics
        if successful_durations:
            return BenchmarkSummary(
                name=self.name,
                category=self.category,
                total_runs=self.benchmark_runs,
                successful_runs=len(successful_durations),
                failed_runs=failed_runs,
                min_ms=min(successful_durations),
                max_ms=max(successful_durations),
                avg_ms=statistics.mean(successful_durations),
                median_ms=statistics.median(successful_durations),
                p95_ms=self._percentile(successful_durations, 95),
                p99_ms=self._percentile(successful_durations, 99),
                std_dev_ms=statistics.stdev(successful_durations) if len(successful_durations) > 1 else 0.0,
                throughput=1000.0 / statistics.mean(successful_durations) if successful_durations else None
            )
        else:
            return BenchmarkSummary(
                name=self.name,
                category=self.category,
                total_runs=self.benchmark_runs,
                successful_runs=0,
                failed_runs=failed_runs,
                min_ms=0.0,
                max_ms=0.0,
                avg_ms=0.0,
                median_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                std_dev_ms=0.0,
                throughput=None
            )
    
    def _percentile(self, data: List[float], p: int) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class BenchmarkSuite:
    """
    Comprehensive benchmarking suite for running multiple benchmarks.
    """
    def __init__(self):
        self.benchmarks: Dict[str, Benchmark] = {}
        self.summaries: Dict[str, BenchmarkSummary] = {}
        self._lock = threading.Lock()
    
    def register_benchmark(self, benchmark: Benchmark):
        """Register a benchmark to the suite."""
        with self._lock:
            self.benchmarks[benchmark.name] = benchmark
    
    def benchmark(self, 
                name: str,
                category: BenchmarkCategory,
                warmup_runs: int = 3,
                benchmark_runs: int = 10,
                timeout: float = 30.0):
        """Decorator for registering benchmarks."""
        def decorator(func):
            benchmark = Benchmark(
                name=name,
                category=category,
                func=func,
                warmup_runs=warmup_runs,
                benchmark_runs=benchmark_runs,
                timeout=timeout
            )
            self.register_benchmark(benchmark)
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
    
    async def run_benchmark(self, name: str) -> Optional[BenchmarkSummary]:
        """Run a specific benchmark by name."""
        benchmark = self.benchmarks.get(name)
        if not benchmark:
            return None
        
        summary = await benchmark.run()
        self.summaries[name] = summary
        return summary
    
    async def run_all(self) -> Dict[str, BenchmarkSummary]:
        """Run all registered benchmarks."""
        results = {}
        
        for name, benchmark in self.benchmarks.items():
            print(f"Running benchmark: {name}...")
            summary = await benchmark.run()
            results[name] = summary
            self.summaries[name] = summary
            print(f"  Completed: {summary.avg_ms:.2f}ms avg ({summary.successful_runs}/{summary.total_runs} successful)")
        
        return results
    
    async def run_category(self, category: BenchmarkCategory) -> Dict[str, BenchmarkSummary]:
        """Run all benchmarks in a specific category."""
        results = {}
        
        for name, benchmark in self.benchmarks.items():
            if benchmark.category == category:
                print(f"Running benchmark: {name}...")
                summary = await benchmark.run()
                results[name] = summary
                self.summaries[name] = summary
                print(f"  Completed: {summary.avg_ms:.2f}ms avg")
        
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all benchmark results."""
        return {
            "total_benchmarks": len(self.benchmarks),
            "completed_benchmarks": len(self.summaries),
            "results": {name: summary.to_dict() for name, summary in self.summaries.items()}
        }
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive benchmark report."""
        report_lines = [
            "=" * 80,
            "REDOPS-AI PERFORMANCE BENCHMARK REPORT",
            "=" * 80,
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Benchmarks: {len(self.benchmarks)}",
            f"Completed: {len(self.summaries)}",
            ""
        ]
        
        # Group by category
        categories = {}
        for name, summary in self.summaries.items():
            category = summary.category.value
            if category not in categories:
                categories[category] = []
            categories[category].append((name, summary))
        
        for category, benchmarks in categories.items():
            report_lines.append(f"\n{category.upper()}")
            report_lines.append("-" * 80)
            
            for name, summary in benchmarks:
                report_lines.append(f"\n{name}:")
                report_lines.append(f"  Average: {summary.avg_ms:.2f}ms")
                report_lines.append(f"  Median: {summary.median_ms:.2f}ms")
                report_lines.append(f"  P95: {summary.p95_ms:.2f}ms")
                report_lines.append(f"  P99: {summary.p99_ms:.2f}ms")
                report_lines.append(f"  Min/Max: {summary.min_ms:.2f}ms / {summary.max_ms:.2f}ms")
                report_lines.append(f"  Success Rate: {summary.successful_runs}/{summary.total_runs} ({(summary.successful_runs/summary.total_runs)*100:.1f}%)")
                if summary.throughput:
                    report_lines.append(f"  Throughput: {summary.throughput:.2f} ops/sec")
        
        report_text = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
        
        return report_text
    
    def clear_results(self):
        """Clear all benchmark results."""
        self.summaries.clear()
        for benchmark in self.benchmarks.values():
            benchmark.results.clear()


# Global benchmark suite instance
benchmark_suite = BenchmarkSuite()


def get_benchmark_suite() -> BenchmarkSuite:
    """Get the global benchmark suite instance."""
    return benchmark_suite


# Predefined benchmarks for core components
async def setup_core_benchmarks():
    """Setup predefined benchmarks for core REDOPS-AI components."""
    from backend.cypher_engine import graph_engine
    from backend.connection_pool import connection_pool
    
    # Graph engine benchmarks
    def graph_query_agents_func():
        return graph_engine.execute_query("MATCH (a:Agent) RETURN a")
    
    benchmark_suite.register_benchmark(Benchmark(
        name="graph_query_agents",
        category=BenchmarkCategory.GRAPH_OPERATIONS,
        func=graph_query_agents_func
    ))
    
    def graph_shortest_path_func():
        return graph_engine.execute_query("shortestPath")
    
    benchmark_suite.register_benchmark(Benchmark(
        name="graph_shortest_path",
        category=BenchmarkCategory.GRAPH_OPERATIONS,
        func=graph_shortest_path_func
    ))
    
    def graph_add_node_func():
        return graph_engine.add_node("test-node", ["Test"], {"prop": "value"})
    
    benchmark_suite.register_benchmark(Benchmark(
        name="graph_add_node",
        category=BenchmarkCategory.GRAPH_OPERATIONS,
        func=graph_add_node_func
    ))
    
    # Memory operation benchmarks
    def list_operations_func():
        return [i for i in range(10000)]
    
    benchmark_suite.register_benchmark(Benchmark(
        name="list_operations",
        category=BenchmarkCategory.MEMORY_OPERATIONS,
        func=list_operations_func
    ))
    
    def dict_operations_func():
        return {f"key_{i}": f"value_{i}" for i in range(10000)}
    
    benchmark_suite.register_benchmark(Benchmark(
        name="dict_operations",
        category=BenchmarkCategory.MEMORY_OPERATIONS,
        func=dict_operations_func
    ))
    
    # Compute intensive benchmarks
    def compute_intensive_func():
        return sum([i for i in range(1000)])
    
    benchmark_suite.register_benchmark(Benchmark(
        name="compute_intensive",
        category=BenchmarkCategory.COMPUTE_INTENSIVE,
        func=compute_intensive_func
    ))


@asynccontextmanager
async def benchmark_context():
    """Context manager for running benchmarks with automatic cleanup."""
    await setup_core_benchmarks()
    try:
        yield benchmark_suite
    finally:
        benchmark_suite.clear_results()


async def run_performance_benchmark(output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Run complete performance benchmark suite and generate report.
    """
    await setup_core_benchmarks()
    
    print("Starting REDOPS-AI Performance Benchmark Suite...")
    print("=" * 80)
    
    results = await benchmark_suite.run_all()
    
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    
    report = benchmark_suite.generate_report(output_file)
    print(report)
    
    if output_file:
        print(f"\nReport saved to: {output_file}")
    
    return benchmark_suite.get_summary()