# ring_buffer

The `ring_buffer` component realizes a minimal bounded circular FIFO buffer with overwrite eviction on capacity exhaustion for ultra-fast smoke testing and agent efficiency profiling.

## Architecture

The benchmark contains a single interface component and a single concrete implementation component:

1. **`ring_buffer`**: Defines the abstract `RingBuffer` protocol and `BufferError` exception hierarchy.
2. **`ring_buffer_impl`**: Implements the circular buffer using `collections.deque` with bounded capacity, wrap-around overwrite semantics, and empty/full state queries (~35 LOC).
