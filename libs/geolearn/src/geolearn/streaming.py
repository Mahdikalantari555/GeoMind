"""Sliding window streaming data structures and updates for online learning."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from typing import Any, Generic, TypeVar

import numpy as np

from geolearn.classifier import OnlineClassifier

T = TypeVar("T")


class StreamingWindow(Generic[T]):
    """Fixed-size FIFO sliding window discarding oldest elements beyond max_size."""

    def __init__(self, max_size: int = 100) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        self.max_size = int(max_size)
        self._buffer: deque[Any] = deque(maxlen=self.max_size)

    def add(self, item_or_embedding: Any, label: Any = None) -> None:
        """Add an item or (embedding, label) pair to the window."""
        if label is not None:
            self._buffer.append((np.asarray(item_or_embedding, dtype=np.float32), int(label)))
        else:
            self._buffer.append(item_or_embedding)

    def append(self, item_or_embedding: Any, label: Any = None) -> None:
        self.add(item_or_embedding, label=label)

    @property
    def is_full(self) -> bool:
        return len(self._buffer) >= self.max_size

    def items(self) -> list[Any]:
        """Return all items in FIFO insertion order."""
        return list(self._buffer)

    def get_arrays(self) -> tuple[np.ndarray, np.ndarray | None]:
        """Convert stored (embedding, label) pairs to NumPy arrays (X, y)."""
        if not self._buffer:
            return np.empty((0, 0), dtype=np.float32), None

        first = self._buffer[0]
        if isinstance(first, tuple) and len(first) == 2:
            X_list = [item[0] for item in self._buffer]
            y_list = [item[1] for item in self._buffer]
            return np.asarray(X_list, dtype=np.float32), np.asarray(y_list, dtype=np.int64)

        return np.asarray(list(self._buffer), dtype=np.float32), None

    def update_classifier(
        self,
        classifier: OnlineClassifier,
        batch_size: int = 10,
    ) -> int:
        """Update an online classifier incrementally with all samples currently in the window."""
        X, y = self.get_arrays()
        if len(X) == 0 or y is None:
            return 0

        n_samples = len(X)
        for i in range(0, n_samples, batch_size):
            batch_X = X[i : i + batch_size]
            batch_y = y[i : i + batch_size]
            classifier.partial_fit(batch_X, batch_y)

        return n_samples

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._buffer)


__all__ = ["StreamingWindow"]
