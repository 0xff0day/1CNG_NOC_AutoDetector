"""
Multi-threading utilities for concurrent device polling.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ThreadPoolManager:
    """Manages thread pool for concurrent operations."""
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
    
    def start(self):
        """Initialize thread pool."""
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
    
    def stop(self):
        """Shutdown thread pool."""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
    
    def map(self, func: Callable, items: List[Any]) -> List[Any]:
        """Execute function over items in parallel."""
        if not self._executor:
            self.start()
        
        results = []
        futures = {self._executor.submit(func, item): item for item in items}
        
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {item}: {e}")
                results.append(None)
        
        return results
