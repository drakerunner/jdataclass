from collections import ChainMap, UserDict
from importlib import import_module
from types import UnionType
from typing import (
    Any,
    Sequence,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)


def get_type_hints_with_module_refs(obj: Any) -> "TypeHints":
    """Get type hints including obj module in localns

    Args:
        obj (Any):

    Returns:
        TypeHints:

    >>> from dataclasses import dataclass
    >>> from typing import Optional
    >>> from importlib import import_module
    ...
    >>> @dataclass
    ... class Owner:
    ...     name: str
    ...     pet: Optional["Pet"]
    ...
    >>> def create_pet(name: str) -> "Pet":
    ...     return Pet(name)
    ...
    >>> @dataclass
    ... class Pet:
    ...     name: str
    ...
    >>> mod = import_module(get_type_hints_with_module_refs.__module__)
    >>> setattr(mod, Owner.__name__, Owner)
    >>> setattr(mod, Pet.__name__, Pet)

    >>> { k: v.__name__
    ...     for k, v
    ...     in get_type_hints_with_module_refs(Owner).items()
    ... }
    {'name': 'str', 'pet': 'Pet'}

    >>> { k: v.__name__
    ...     for k, v
    ...     in get_type_hints_with_module_refs(create_pet).items()
    ... }
    {'name': 'str', 'return': 'Pet'}

    """
    localns = locals()
    if obj.__module__:
        localns = cast(
            dict[str, Any],
            ChainMap(vars(import_module(obj.__module__)), localns),
        )

    return TypeHints(
        get_type_hints(
            obj,
            localns=localns,
        )
    )


class TypeHints(UserDict[str, type]):
    def __getitem__(self, key: str) -> type:
        return self._get_real_type(super().__getitem__(key))

    def _get_real_type(self, field_type: Any) -> Any:
        origin = get_origin(field_type)
        args: Sequence[type] = get_args(field_type)

        if origin and args:
            if origin is Union or origin is UnionType:
                no_optional = [
                    a for a in args if a is not type(None)  # noqa:E721
                ]
                if len(no_optional) == 1:
                    return no_optional[0]
            elif issubclass(origin, Sequence):
                if len(args) == 1:
                    return self._get_real_type(args[0])

        return field_type


if __name__ == "__main__":
    import doctest

    doctest.testmod()
