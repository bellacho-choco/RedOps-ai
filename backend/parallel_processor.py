"""
====================================================================
PROJECT REDOPS-AI - ADVANCED PARALLEL PROCESSING ENGINE
High-performance task execution with rate limiting, error handling, and result aggregation
====================================================================
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading
from enum import Enum
from contextlib import asynccontextmanager


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of a parallel task execution."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    start_time: float = 0.0
    end_time: float = 0.0
    retry_count: int = 0
    
    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time > 0 else 0.0


@dataclass
class ParallelTask:
    """Represents a task to be executed in parallel."""
    task_id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: int = 0  # Higher priority tasks execute first
    max_retries: int = 0
    timeout: float = 30.0
    result: Optional[TaskResult] = None


class RateLimiter:
    """
    Token bucket rate limiter for controlling task execution rate.
    """
    def __init__(self, rate: float, burst: int = 10):
        self.rate = rate  # tokens per second
        self.burst = burst  # maximum bucket size
        self.tokens = burst
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    async def acquire(self, tokens: int = 1):
        """Acquire tokens from the bucket, waiting if necessary."""
        while True:
            async with asyncio.Lock():
                with self._lock:
                    now = time.time()
                    elapsed = now - self.last_update
                    self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                    self.last_update = now
                    
                    if self.tokens >= tokens:
                        self.tokens -= tokens
                        return
            
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


class ParallelProcessor:
    """
    Advanced parallel processing engine with rate limiting, 
    priority queues, and comprehensive error handling.
    """
    def __init__(self, 
                 max_workers: int = 10,
                 max_concurrent: int = 5,
                 rate_limit: Optional[float] = None,
                 enable_thread_pool: bool = True):
        self.max_workers = max_workers
        self.max_concurrent = max_concurrent
        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        self.enable_thread_pool = enable_thread_pool
        
        # Task queues
        self.pending_tasks: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, ParallelTask] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        
        # Thread pool for CPU-bound tasks
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers) if enable_thread_pool else None
        
        # Control
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        
        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "total_duration_ms": 0.0
        }
    
    async def start(self):
        """Start the parallel processor workers."""
        if self._running:
            return
        
        self._running = True
        self._worker_tasks = [
            asyncio.create_task(self._worker(worker_id))
            for worker_id in range(self.max_concurrent)
        ]
    
    async def stop(self):
        """Stop the parallel processor gracefully."""
        self._running = False
        
        # Cancel all running tasks
        for task in self.running_tasks.values():
            if task.result:
                task.result.status = TaskStatus.CANCELLED
                self.completed_tasks[task.task_id] = task.result
                self.stats["cancelled"] += 1
        
        # Wait for workers to finish
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # Shutdown thread pool
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
    
    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks from the queue."""
        while self._running:
            try:
                # Get task from queue (timeout to allow checking _running)
                priority, task = await asyncio.wait_for(
                    self.pending_tasks.get(), timeout=1.0
                )
                
                # Apply rate limiting if configured
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                # Execute task
                await self._execute_task(task)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
    
    async def _execute_task(self, task: ParallelTask):
        """Execute a single task with retry logic and timeout."""
        task.result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.RUNNING,
            start_time=time.time()
        )
        
        self.running_tasks[task.task_id] = task
        
        for attempt in range(task.max_retries + 1):
            try:
                # Execute with timeout
                if asyncio.iscoroutinefunction(task.func):
                    result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs),
                        timeout=task.timeout
                    )
                elif self.thread_pool:
                    # Run CPU-bound function in thread pool
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.thread_pool,
                            lambda: task.func(*task.args, **task.kwargs)
                        ),
                        timeout=task.timeout
                    )
                else:
                    # Synchronous execution (not recommended for I/O)
                    result = task.func(*task.args, **task.kwargs)
                
                # Success
                task.result.status = TaskStatus.COMPLETED
                task.result.result = result
                task.result.retry_count = attempt
                break
                
            except asyncio.TimeoutError:
                if attempt == task.max_retries:
                    task.result.status = TaskStatus.FAILED
                    task.result.error = TimeoutError(f"Task timed out after {task.timeout}s")
                else:
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                    
            except Exception as e:
                if attempt == task.max_retries:
                    task.result.status = TaskStatus.FAILED
                    task.result.error = e
                else:
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        task.result.end_time = time.time()
        
        # Update statistics
        self.completed_tasks[task.task_id] = task.result
        del self.running_tasks[task.task_id]
        
        if task.result.status == TaskStatus.COMPLETED:
            self.stats["completed"] += 1
            self.stats["total_duration_ms"] += task.result.duration_ms
        else:
            self.stats["failed"] += 1
    
    async def submit_task(self, task: ParallelTask) -> str:
        """Submit a task for parallel execution."""
        self.stats["total_tasks"] += 1
        
        # Use negative priority for max-heap behavior (higher priority first)
        priority = -task.priority
        await self.pending_tasks.put((priority, task))
        
        return task.task_id
    
    async def submit_func(self, func: Callable, *args, 
                         task_id: Optional[str] = None,
                         priority: int = 0,
                         max_retries: int = 0,
                         timeout: float = 30.0,
                         **kwargs) -> str:
        """Convenience method to submit a function as a task."""
        task = ParallelTask(
            task_id=task_id or str(uuid.uuid4()),
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            timeout=timeout
        )
        return await self.submit_task(task)
    
    async def submit_batch(self, funcs: List[Tuple[Callable, tuple, dict]],
                          priority: int = 0,
                          max_retries: int = 0,
                          timeout: float = 30.0) -> List[str]:
        """Submit multiple functions as a batch of tasks."""
        task_ids = []
        
        for func, args, kwargs in funcs:
            task = ParallelTask(
                task_id=str(uuid.uuid4()),
                func=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                max_retries=max_retries,
                timeout=timeout
            )
            task_id = await self.submit_task(task)
            task_ids.append(task_id)
        
        return task_ids
    
    async def get_result(self, task_id: str, timeout: float = 60.0) -> Optional[TaskResult]:
        """Wait for and return the result of a specific task."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            await asyncio.sleep(0.1)
        
        return None
    
    async def wait_for_all(self, task_ids: List[str], timeout: float = 300.0) -> Dict[str, TaskResult]:
        """Wait for all tasks to complete and return their results."""
        results = {}
        start_time = time.time()
        
        while len(results) < len(task_ids) and time.time() - start_time < timeout:
            for task_id in task_ids:
                if task_id not in results and task_id in self.completed_tasks:
                    results[task_id] = self.completed_tasks[task_id]
            await asyncio.sleep(0.1)
        
        # Add any pending tasks as failed if timeout
        for task_id in task_ids:
            if task_id not in results:
                results[task_id] = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error=TimeoutError("Task did not complete in time")
                )
        
        return results
    
    async def wait_for_any(self, task_ids: List[str], timeout: float = 60.0) -> Optional[TaskResult]:
        """Wait for any of the tasks to complete and return the first result."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for task_id in task_ids:
                if task_id in self.completed_tasks:
                    return self.completed_tasks[task_id]
            await asyncio.sleep(0.05)
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current processor statistics."""
        completed = self.stats["completed"]
        avg_duration = (self.stats["total_duration_ms"] / completed) if completed > 0 else 0.0
        
        return {
            "tasks": {
                "total": self.stats["total_tasks"],
                "pending": self.pending_tasks.qsize(),
                "running": len(self.running_tasks),
                "completed": completed,
                "failed": self.stats["failed"],
                "cancelled": self.stats["cancelled"]
            },
            "performance": {
                "avg_duration_ms": round(avg_duration, 2),
                "success_rate": round((completed / self.stats["total_tasks"]) * 100, 2) if self.stats["total_tasks"] > 0 else 0.0
            },
            "configuration": {
                "max_workers": self.max_workers,
                "max_concurrent": self.max_concurrent,
                "rate_limited": self.rate_limiter is not None,
                "thread_pool_enabled": self.enable_thread_pool
            }
        }
    
    def clear_completed(self):
        """Clear completed task results to free memory."""
        self.completed_tasks.clear()


# Global parallel processor instance
parallel_processor = ParallelProcessor(
    max_workers=10,
    max_concurrent=5,
    rate_limit=10.0  # 10 operations per second
)


@asynccontextmanager
async def get_parallel_processor():
    """Context manager for using the parallel processor."""
    await parallel_processor.start()
    try:
        yield parallel_processor
    finally:
        await parallel_processor.stop()