"""Bidirectional collection helpers and recognizers/generators for Pretense."""

import random
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

from pretense.context import get_current_draw
from pretense.sentinels import NotBound, NotBoundType

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def make_tup(*choosers: Callable[..., Any]) -> Callable[..., Optional[Tuple[Any, ...]]]:
    """Compose multiple argument recognizers/generators into a single joint tuple chooser.
    
    If any individual chooser returns None, the combined chooser returns None (rejection).
    """
    def combined(state: Any, this: Any, *args: Any) -> Optional[Tuple[Any, ...]]:
        res: List[Any] = []
        for chooser, arg in zip(choosers, args):
            val = chooser(state, this, arg)
            if val is None:
                return None
            res.append(val)
        return tuple(res)
    return combined


def choose_weighted(*weighted_options: Tuple[float, Callable[[Any], Any]]) -> Any:
    """Statistical selection across weighted alternatives.
    
    Under Hypothesis, uses st.frequency() to allow full byte-stream shrinking.
    Outside Hypothesis, falls back to random.choices.
    """
    draw = get_current_draw()
    if draw is not None:
        try:
            import hypothesis.strategies as st
            st_mod: Any = st
            freq_strategies = []
            for weight, builder in weighted_options:
                int_weight = max(1, int(round(weight * 100)))
                try:
                    strat = builder(st_mod)
                    if isinstance(strat, st.SearchStrategy):
                        freq_strategies.append((int_weight, strat))
                    else:
                        freq_strategies.append((int_weight, st.just(strat)))
                except Exception:
                    freq_strategies.append((int_weight, st.just(builder(random))))
            return draw(st_mod.frequency(freq_strategies))
        except ImportError:
            pass

    # Deterministic fallback / PRNG
    weights = [w for w, _ in weighted_options]
    builders = [b for _, b in weighted_options]
    chosen_builder = random.choices(builders, weights=weights, k=1)[0]
    return chosen_builder(random)


class PretenseSet(Set[T]):
    """State collection tracking rolling tombstones and providing bidirectional helpers."""

    def __init__(self, elements: Any = ()) -> None:
        super().__init__(elements)
        self._tombstones: deque[T] = deque(maxlen=50)

    def remove(self, element: T) -> None:
        super().remove(element)
        self._tombstones.append(element)

    def discard(self, element: object) -> None:
        if element in self:
            super().discard(element)
            self._tombstones.append(element)  # type: ignore

    def get_in(self, val: Union[T, NotBoundType]) -> Optional[T]:
        """Recognize membership or generate an existing element from the set."""
        if isinstance(val, NotBoundType):
            if not self:
                return None
            draw = get_current_draw()
            if draw is not None:
                try:
                    import hypothesis.strategies as st
                    return draw(st.sampled_from(list(self)))
                except ImportError:
                    pass
            return next(iter(self))
        return val if val in self else None

    def get_not_in(self, val: Union[T, NotBoundType], prefix: str = "item_") -> Optional[T]:
        """Recognize non-membership or generate an absent element across 4 tiers."""
        if isinstance(val, NotBoundType):
            draw = get_current_draw()
            if draw is not None:
                try:
                    import hypothesis.strategies as st
                    # Tier 1: The Graveyard (Tombstone History) - 40% probability if available
                    if self._tombstones and draw(st.booleans()) and draw(st.booleans()):
                        candidate = draw(st.sampled_from(list(self._tombstones)))
                        if candidate not in self:
                            return candidate

                    # Tier 2: Near-Miss Mutations - 30% probability if string elements exist
                    if self and all(isinstance(x, str) for x in self) and draw(st.booleans()):
                        base = str(draw(st.sampled_from(list(self))))
                        mutation_type = draw(st.integers(0, 3))
                        if mutation_type == 0:
                            candidate_str = base.upper() if base.islower() else base.lower()
                        elif mutation_type == 1:
                            candidate_str = base + " "
                        elif mutation_type == 2:
                            candidate_str = "_" + base
                        else:
                            candidate_str = base + "_alt"
                        if candidate_str not in self:
                            return candidate_str  # type: ignore

                    # Tier 3: Open Universe Fuzzing
                    if not self or all(isinstance(x, str) for x in self):
                        fresh_str = draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in self))
                        return fresh_str  # type: ignore
                except ImportError:
                    pass

            # Tier 4: Deterministic Sequential Fallback
            idx = len(self)
            candidate = f"{prefix}{idx}"
            while candidate in self:
                idx += 1
                candidate = f"{prefix}{idx}"
            return candidate  # type: ignore

        return val if val not in self else None

    def get_subset(self, val: Union[Set[T], NotBoundType]) -> Optional[Set[T]]:
        """Recognize a subset or generate a valid subset from this set."""
        if isinstance(val, NotBoundType):
            draw = get_current_draw()
            if draw is not None:
                try:
                    import hypothesis.strategies as st
                    return set(draw(st.lists(st.sampled_from(list(self)), unique=True))) if self else set()
                except ImportError:
                    pass
            return set()
        return val if isinstance(val, (set, frozenset)) and val.issubset(self) else None


class PretenseDict(Dict[K, V]):
    """Dictionary collection tracking key tombstones for bidirectional key recognition/generation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tombstones: deque[K] = deque(maxlen=50)

    def __delitem__(self, key: K) -> None:
        super().__delitem__(key)
        self._tombstones.append(key)

    def pop(self, key: K, *args: Any) -> V:
        res = super().pop(key, *args)
        self._tombstones.append(key)
        return res

    def get_key_in(self, key: Union[K, NotBoundType]) -> Optional[K]:
        """Recognize key existence or generate an existing key."""
        if isinstance(key, NotBoundType):
            if not self:
                return None
            draw = get_current_draw()
            if draw is not None:
                try:
                    import hypothesis.strategies as st
                    return draw(st.sampled_from(list(self.keys())))
                except ImportError:
                    pass
            return next(iter(self.keys()))
        return key if key in self else None

    def get_key_not_in(self, key: Union[K, NotBoundType], prefix: str = "key_") -> Optional[K]:
        """Recognize key absence or generate an absent key."""
        if isinstance(key, NotBoundType):
            draw = get_current_draw()
            if draw is not None:
                try:
                    import hypothesis.strategies as st
                    if self._tombstones and draw(st.booleans()):
                        cand = draw(st.sampled_from(list(self._tombstones)))
                        if cand not in self:
                            return cand
                    if not self or all(isinstance(k, str) for k in self.keys()):
                        return draw(st.text(min_size=1, max_size=10).filter(lambda s: s not in self))  # type: ignore
                except ImportError:
                    pass
            idx = len(self)
            cand_str = f"{prefix}{idx}"
            while cand_str in self:
                idx += 1
                cand_str = f"{prefix}{idx}"
            return cand_str  # type: ignore
        return key if key not in self else None
