"""
Tile Cache for OpenVisus
Implements predictive tile caching to prefetch surrounding tiles for smooth panning.
"""

import numpy as np
import threading
import time
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional, Callable, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TileKey:
    """Unique identifier for a tile"""
    x: int
    y: int
    z: int  # zoom level (resolution)
    timestep: int
    field: str
    
    def __hash__(self):
        return hash((self.x, self.y, self.z, self.timestep, self.field))
    
    def __eq__(self, other):
        if not isinstance(other, TileKey):
            return False
        return (self.x, self.y, self.z, self.timestep, self.field) == \
               (other.x, other.y, other.z, other.timestep, other.field)
    
    def __repr__(self):
        return f"TileKey(x={self.x}, y={self.y}, z={self.z}, t={self.timestep}, f={self.field})"


@dataclass
class TileData:
    """Cached tile with metadata"""
    data: np.ndarray
    logic_box: List[List[float]]
    timestamp: float
    loading: bool = False
    
    def __repr__(self):
        return f"TileData(shape={self.data.shape if self.data is not None else None}, loading={self.loading})"


class TileCache:
    """
    Multi-tile cache for smooth panning/zooming.
    Prefetches tiles in a 3x3 grid around current viewport for immediate display.
    """
    
    def __init__(self, max_tiles=27, prefetch_radius=1, enabled=True):
        """
        Args:
            max_tiles: Maximum number of tiles to keep in cache (default: 27 = 3x3x3)
            prefetch_radius: How many tiles to prefetch in each direction (1 = 3x3 grid)
            enabled: Enable/disable tile caching (can be toggled at runtime)
        """
        self.cache: OrderedDict[TileKey, TileData] = OrderedDict()
        self.max_tiles = max_tiles
        self.prefetch_radius = prefetch_radius
        self.enabled = enabled
        self.lock = threading.Lock()
        self.loading_tiles = set()
        self.loader_thread = None
        self.stop_loading = threading.Event()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'prefetches': 0,
            'evictions': 0
        }
        
        logger.info(f"TileCache initialized: max_tiles={max_tiles}, prefetch_radius={prefetch_radius}, enabled={enabled}")
    
    def is_enabled(self) -> bool:
        """Check if caching is enabled"""
        return self.enabled
    
    def set_enabled(self, enabled: bool):
        """Enable or disable caching"""
        self.enabled = enabled
        if not enabled:
            self.stop_prefetch()
            logger.info("TileCache disabled")
        else:
            logger.info("TileCache enabled")
    
    def get_tile(self, key: TileKey) -> Optional[TileData]:
        """
        Get tile from cache if available.
        Returns None if not cached or still loading.
        """
        if not self.enabled:
            return None
            
        with self.lock:
            if key in self.cache:
                tile_data = self.cache[key]
                # Move to end (LRU)
                self.cache.move_to_end(key)
                
                if not tile_data.loading:
                    self.stats['hits'] += 1
                    logger.debug(f"Cache HIT: {key}")
                    return tile_data
                else:
                    logger.debug(f"Cache LOADING: {key}")
                    return None
            
            self.stats['misses'] += 1
            logger.debug(f"Cache MISS: {key}")
            return None
    
    def put_tile(self, key: TileKey, data: np.ndarray, logic_box: List[List[float]]):
        """Add tile to cache"""
        if not self.enabled:
            return
            
        with self.lock:
            self.cache[key] = TileData(
                data=data,
                logic_box=logic_box,
                timestamp=time.time(),
                loading=False
            )
            self.cache.move_to_end(key)
            
            # Remove oldest tiles if over limit (LRU eviction)
            while len(self.cache) > self.max_tiles:
                evicted_key, _ = self.cache.popitem(last=False)
                self.stats['evictions'] += 1
                logger.debug(f"Cache EVICTED: {evicted_key}")
    
    def mark_loading(self, key: TileKey):
        """Mark a tile as currently being loaded"""
        if not self.enabled:
            return
            
        with self.lock:
            if key not in self.cache:
                self.cache[key] = TileData(
                    data=None,
                    logic_box=None,
                    timestamp=time.time(),
                    loading=True
                )
                self.loading_tiles.add(key)
    
    def clear_loading(self, key: TileKey):
        """Clear loading marker"""
        with self.lock:
            self.loading_tiles.discard(key)
            # Remove loading placeholder if actual data wasn't put
            if key in self.cache and self.cache[key].loading:
                del self.cache[key]
    
    def is_loading(self, key: TileKey) -> bool:
        """Check if a tile is currently being loaded"""
        with self.lock:
            return key in self.loading_tiles
    
    def get_prefetch_tiles(self, center_key: TileKey) -> List[TileKey]:
        """
        Get list of tiles to prefetch around center tile.
        Returns tiles in a (2*radius+1) x (2*radius+1) grid.
        Priority: center first, then by distance.
        """
        tiles = []
        r = self.prefetch_radius
        
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                tile_key = TileKey(
                    x=center_key.x + dx,
                    y=center_key.y + dy,
                    z=center_key.z,
                    timestep=center_key.timestep,
                    field=center_key.field
                )
                tiles.append(tile_key)
        
        # Sort by distance from center (Manhattan distance)
        tiles.sort(key=lambda t: abs(t.x - center_key.x) + abs(t.y - center_key.y))
        
        return tiles
    
    def prefetch_async(self, center_key: TileKey, loader_func: Callable[[TileKey], Optional[TileData]]):
        """
        Start asynchronous prefetching of tiles around center.
        Uses multiple threads for parallel loading (MUCH faster).
        
        Args:
            center_key: Current viewport tile
            loader_func: Function(TileKey) -> TileData to load tile data
        """
        if not self.enabled:
            return
        
        import concurrent.futures
        
        def load_single_tile(tile_key):
            """Load a single tile (runs in thread pool)"""
            # Skip if already in cache or loading
            with self.lock:
                if tile_key in self.cache:
                    if not self.cache[tile_key].loading:
                        return  # Already have valid data
                if tile_key in self.loading_tiles:
                    return  # Already loading
            
            try:
                # Mark as loading
                self.mark_loading(tile_key)
                
                # Load tile (this is the slow part - runs in parallel)
                tile_data = loader_func(tile_key)
                
                # Store in cache if successful
                if tile_data is not None:
                    self.put_tile(tile_key, tile_data.data, tile_data.logic_box)
                    self.stats['prefetches'] += 1
                    logger.debug(f"✓ Prefetched: {tile_key}")
                
            except Exception as e:
                logger.error(f"Error loading tile {tile_key}: {e}")
            finally:
                self.clear_loading(tile_key)
        
        def load_tiles_parallel():
            """Main prefetch function - loads tiles in parallel"""
            tiles_to_load = self.get_prefetch_tiles(center_key)
            logger.debug(f"Prefetching {len(tiles_to_load)} tiles around {center_key} (parallel)")
            
            # Use ThreadPoolExecutor for parallel loading (8 threads - balanced)
            with concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="TileLoader") as executor:
                # Submit all tiles for parallel loading
                futures = [executor.submit(load_single_tile, tile_key) for tile_key in tiles_to_load]
                
                # Wait for all to complete (or stop signal)
                for future in concurrent.futures.as_completed(futures):
                    if self.stop_loading.is_set():
                        logger.debug("Prefetch stopped - cancelling remaining")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        future.result()  # Raise any exceptions
                    except Exception as e:
                        logger.error(f"Prefetch error: {e}")
        
        # Stop previous loading if running
        self.stop_prefetch()
        
        # Start new loading thread (manages thread pool)
        self.stop_loading.clear()
        self.loader_thread = threading.Thread(target=load_tiles_parallel, daemon=True, name="TilePrefetch")
        self.loader_thread.start()
    
    def stop_prefetch(self):
        """Stop any ongoing prefetch operations"""
        if self.loader_thread and self.loader_thread.is_alive():
            self.stop_loading.set()
            self.loader_thread.join(timeout=1.0)
            logger.debug("Prefetch thread stopped")
    
    def clear(self):
        """Clear all cached tiles and stop prefetching"""
        self.stop_prefetch()
        with self.lock:
            self.cache.clear()
            self.loading_tiles.clear()
        logger.info("TileCache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'enabled': self.enabled,
                'size': len(self.cache),
                'max_tiles': self.max_tiles,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': f"{hit_rate:.1f}%",
                'prefetches': self.stats['prefetches'],
                'evictions': self.stats['evictions'],
                'loading': len(self.loading_tiles)
            }
    
    def reset_stats(self):
        """Reset statistics counters"""
        with self.lock:
            self.stats = {
                'hits': 0,
                'misses': 0,
                'prefetches': 0,
                'evictions': 0
            }
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop_prefetch()
