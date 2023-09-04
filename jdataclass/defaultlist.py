from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Optional,
    SupportsIndex,
    TypeVar,
    cast,
    overload,
)

T = TypeVar("T")


class defaultlist(
    list[T],
    Generic[T],
):  # pylint: disable=invalid-name
    """List that resizes itself when an index out of range is accessed.

    Set value at index out of range
    >>> l = defaultlist()
    >>> l[1] = 1
    >>> l
    [None, 1]

    Get value from index out of range
    >>> l = defaultlist()
    >>> l[1]

    """

    def __init__(
        self,
        default_factory: Optional[Callable[[], T]] = None,
    ) -> None:
        self.default_factory = default_factory or (lambda: None)

    @overload
    def __getitem__(self, __i: SupportsIndex) -> T:  # pragma: no cover
        ...

    @overload
    def __getitem__(self, __s: slice) -> list[T]:  # pragma: no cover
        ...

    def __getitem__(self, key: Any) -> Any:
        self.__ensure_length(key + 1)

        return cast(Any, super().__getitem__(key))

    @overload
    def __setitem__(
        self, key: SupportsIndex, value: T
    ) -> None:  # pragma: no cover
        ...

    @overload
    def __setitem__(
        self, key: slice, value: Iterable[T]
    ) -> None:  # pragma: no cover
        ...

    def __setitem__(self, key: Any, value: Any):
        self.__ensure_length(key + 1)

        super().__setitem__(key, value)

    def __ensure_length(self, max_length: int):
        if len(self) < max_length:
            self += [self.default_factory()] * (max_length - len(self))


if __name__ == "__main__":
    import doctest

    doctest.testmod()
