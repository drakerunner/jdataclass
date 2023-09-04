from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class defaultdict(
    dict[K, V],
    Generic[K, V],
):  # pylint: disable=invalid-name
    """defaultdict for JSON build.

    Return None when property not in dict
    >>> d = defaultdict()
    >>> d["my-prop"]
    """

    def __missing__(self, key: K):
        return None


if __name__ == "__main__":
    import doctest

    doctest.testmod()
