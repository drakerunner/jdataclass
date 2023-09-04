from inspect import isclass
from typing import Any, Callable, Generic, TypeVar, overload

from jdataclass.constants import JPROPERTIES
from jdataclass.jfield import JField

T = TypeVar("T")


class JProperty(Generic[T]):
    def __init__(
        self,
        fget: Callable[[Any], T],
        fset: Callable[[Any, T], None] | None,
        path: str | None,
    ) -> None:
        self.property = property(fget, fset)
        self.path = path

    def __set_name__(self, owner: Any, name: str):
        _jfield = JField(
            name=name,
            path=self.path,
            field_type=self.property.fget.__annotations__.get("return"),
        )

        cls = owner if isclass(owner) else type(owner)
        _jproperties = getattr(cls, JPROPERTIES, tuple[JField, ...]())
        setattr(owner, JPROPERTIES, _jproperties + (_jfield,))

    def setter(self, fset: Callable[[Any, T], None]):
        """Set jproperty setter"""
        self.property = self.property.setter(fset)
        return self

    def __get__(self, obj: Any, objtype: Any) -> T:
        return self.property.__get__(obj, objtype)

    def __set__(self, obj: Any, value: Any):
        self.property.__set__(obj, value)
        self.property.__set__(obj, value)


@overload
def jproperty(fget: Callable[[Any], T]) -> JProperty[T]:  # pragma: no cover
    ...


@overload
def jproperty(
    *,
    fset: Callable[[Any, T], None] | None = None,
    path: str | None = None,
) -> Callable[[Callable[[Any], T]], JProperty[T]]:  # pragma: no cover
    ...


def jproperty(
    fget: Callable[[Any], T] | None = None,
    *,
    fset: Callable[[Any, T], None] | None = None,
    path: str | None = None,
) -> JProperty[T] | Callable[[Callable[[Any], T]], JProperty[T]]:
    """Decorator that creates a property bound to a jfield."""

    def wrap(fget: Callable[[Any], T]):
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

    return tuple()
