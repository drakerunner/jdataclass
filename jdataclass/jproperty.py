from inspect import isclass
from typing import Any, Callable, Generic, ParamSpec, TypeVar, cast, overload

from jdataclass.constants import JPROPERTIES, TEMP_JPROPERTIES
from jdataclass.jfield import JField
from jdataclass.typing_utils import get_type_hints_with_module_refs

T = TypeVar("T")
P = ParamSpec("P")


class JProperty(Generic[T], property):
    def __init__(
        self,
        fget: Callable[P, T],
        fset: Callable[[Any, T], None] | None,
        path: str | None,
    ) -> None:
        super().__init__(fget=cast(Any, fget), fset=fset)
        self.owner: Any = None
        self.name = ""
        self.path = path

    def __set_name__(self, owner: Any, name: str):
        self.owner = owner
        self.name = name
        cls = owner if isclass(owner) else type(owner)
        _jproperties = getattr(
            cls,
            TEMP_JPROPERTIES,
            tuple[JProperty[Any], ...](),
        )
        setattr(owner, TEMP_JPROPERTIES, _jproperties + (self,))

    def asfield(self):
        type_hints = get_type_hints_with_module_refs(self.fget)
        field_type = type_hints.get("return")
        if field_type is None:
            raise ValueError(
                "JProperty must have a return type"
                f": {self.owner.__name__}.{self.name}"
            )

        return JField(
            name=self.name,
            path=self.path,
            field_type=type_hints.get("return"),
        )

    def setter(self, fset: Callable[[Any, T], None]):
        """Set jproperty setter"""
        return JProperty[T](
            fget=cast(Any, self.fget),
            fset=fset,
            path=self.path,
        )


@overload
def jproperty(fget: Callable[P, T]) -> JProperty[T]:  # pragma: no cover
    ...


@overload
def jproperty(
    *,
    fset: Callable[[Any, T], None] | None = None,
    path: str | None = None,
) -> Callable[[Callable[P, T]], JProperty[T]]:  # pragma: no cover
    ...


def jproperty(
    fget: Callable[P, T] | None = None,
    *,
    fset: Callable[[Any, T], None] | None = None,
    path: str | None = None,
) -> JProperty[T] | Callable[[Callable[P, T]], JProperty[T]]:
    """Decorator that creates a property bound to a jfield."""

    def wrap(fget: Callable[P, T]):
        return JProperty[T](fget, fset, path)

    if fget is None:
        return wrap

    return wrap(fget)


def jproperties(class_or_instance: T | type[T]) -> tuple[JField, ...]:
    """Return a tuple describing the jproperties of this dataclass

    Args:
        class_or_instance (T | type[T]):

    Returns:
        tuple[JField, ...]:
    """
    cls = (
        class_or_instance
        if isclass(class_or_instance)
        else type(class_or_instance)
    )
    if _jproperties := getattr(cls, JPROPERTIES, None):
        return _jproperties

    if _jproperties := getattr(cls, TEMP_JPROPERTIES, None):
        _jproperties = cast(tuple[JProperty[Any], ...], _jproperties)
        _jproperties = tuple(p.asfield() for p in _jproperties)
        setattr(cls, JPROPERTIES, _jproperties)
        delattr(cls, TEMP_JPROPERTIES)
        return _jproperties

    return tuple()
