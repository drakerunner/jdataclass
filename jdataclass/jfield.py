from dataclasses import _MISSING_TYPE  # type:ignore
from dataclasses import MISSING, Field, dataclass, field, fields
from importlib import import_module
from inspect import isclass
from types import UnionType  # type:ignore
from typing import (
    Any,
    Callable,
    Mapping,
    Sequence,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from jdataclass.constants import JFIELD_OPTIONS, JFIELDS

T = TypeVar("T")


@dataclass(frozen=True)
class JFieldOptions:
    """Options for jfield."""

    path: str
    parent_ref: bool = field(default=False)


class JField:
    """Json field mapping.

    >>> JField("name", "path")
    JField(name='name', path='path')

    >>> JField("name", "path", str)
    JField(name='name', path='path', field_type='str')
    """

    def __init__(
        self,
        name: str,
        path: str | None = None,
        field_type: type | None = None,
        parent_ref: bool = False,
    ):
        self.name = name
        self.path = path or name
        self.field_type = field_type
        self.parent_ref = parent_ref
        self.__setattr__ = lambda *_: None
        self.__delattr__ = lambda *_: None

    def __repr__(self) -> str:
        if self.field_type:
            return (
                f"JField("
                f"name={self.name!r}, "
                f"path={self.path!r}, "
                f"field_type={self.field_type.__name__!r}"
                ")"
            )

        return f"JField(name={self.name!r}, path={self.path!r})"


if __name__ == "__main__":
    import doctest

    doctest.testmod()


def jfield(
    *,
    path: str | _MISSING_TYPE = MISSING,
    parent_ref: bool | _MISSING_TYPE = MISSING,
    default: T | _MISSING_TYPE = MISSING,
    default_factory: Callable[[], T] | _MISSING_TYPE = MISSING,
    init: bool = True,
    repr: bool = True,  # pylint:disable=redefined-builtin
    hash: bool | None = None,  # pylint:disable=redefined-builtin
    compare: bool = True,
    metadata: Mapping[Any, Any] | None = None,
    kw_only: bool | _MISSING_TYPE = MISSING,
) -> T:
    """Wrapper on top of field function add jfield options to metadata

    Args:
        path (str, optional): path in dictionary to
        get or set values when dsserializing or serializing.

        parent_ref (bool, optional): If true, when
        creating an instance of the object, this property will be set
        with a reference to an object that represents the parent in the
        deserialization hierarchy. See examples for more info.
        Defaults to False.

        default (T, optional): If provided,
        this will be the default value for this field. This is needed
        because the field() call itself replaces the normal position of
        the default value.

        default_factory (Callable[[], T], optional):
        If provided, it must be a zero-argument callable that will be
        called when a default value is needed for this field. Among
        other purposes, this can be used to specify fields with mutable
        default values, as discussed below. It is an error to specify
        both default and default_factory.

        init (bool, optional):
        If true (the default), this field is included as a parameter
        to the generated __init__() method

        repr (bool, optional): If true (the default), this field is
        included in the string returned by the generated __repr__()
        method.

        hash (bool, optional): This can be a bool or None. If true,
        this field is included in the generated __hash__() method.
        If None (the default), use the value of compare: this would
        normally be the expected behavior. A field should be
        considered in the hash if it’s used for comparisons.
        Setting this value to anything other than None is discouraged.

        compare (bool, optional): If true (the default), this field is
        included in the generated equality and comparison methods
        (__eq__(), __gt__(), et al.).

        metadata (Mapping[Any, Any] | None, optional): This can be a
        mapping or None. None is treated as an empty dict. This value
        is wrapped in MappingProxyType() to make it read-only, and
        exposed on the Field object. It is not used at all by Data
        Classes, and is provided as a third-party extension mechanism.
        Multiple third-parties can each have their own key, to use
        as a namespace in the metadata.

        kw_only (bool | _MISSING_TYPE, optional):
        If true, this field will be marked as keyword-only. This is
        used when the generated __init__() method’s parameters are
        computed.

    Returns:
        T: _description_
    """
    if metadata is None:
        metadata = {}

    path = path if path != MISSING else ""
    parent_ref = parent_ref if parent_ref != MISSING else False
    options = JFieldOptions(path, parent_ref)

    metadata |= {JFIELD_OPTIONS: options}

    return field(
        default=default,
        default_factory=default_factory,  # type:ignore
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
        kw_only=kw_only,
    )


def jfields(class_or_instance: T | type[T]) -> tuple[JField, ...]:
    """Return a tuple describing the jfields of this dataclass

    Args:
        class_or_instance (T | type[T]):

    Returns:
        tuple[JField, ...]:

    >>> from dataclasses import dataclass

    >>> @dataclass
    ... class MyClass:
    ...     prop_1: str
    ...     prop_2: list[str]
    ...     prop_3: str | None

    >>> jfields(MyClass)
    (JField(name='prop_1', path='prop_1', field_type='str'), JField(name='prop_2', path='prop_2', field_type='str'), JField(name='prop_3', path='prop_3', field_type='str'))

    >>> @dataclass
    ... class Child:
    ...     name: str

    >>> @dataclass
    ... class Parent:
    ...     name: str
    ...     children: list[Child]

    >>> _jfields = jfields(Parent)
    >>> _jfields
    (JField(name='name', path='name', field_type='str'), JField(name='children', path='children', field_type='Child'))
    """  # noqa: E501 # pylint: disable=line-too-long
    cls = (
        class_or_instance
        if isclass(class_or_instance)
        else type(class_or_instance)
    )
    if _jfields := getattr(cls, str(JFIELDS), None):
        return _jfields

    _jfields = tuple(_build_jfields(cls))
    setattr(cls, str(JFIELDS), _jfields)
    return _jfields


def _build_jfields(cls: type):
    localns = locals()
    if cls.__module__:
        localns = vars(import_module(cls.__module__))

    type_hints = get_type_hints(cls, localns=localns)
    for _field in fields(cls):
        options = _get_jfield_options(_field)

        if not _field.init:
            continue

        yield JField(
            name=_field.name,
            path=options.path,
            field_type=_get_field_type(type_hints, _field.name),
            parent_ref=options.parent_ref,
        )


def _get_field_type(
    type_hints: dict[str, Any],
    field_name: str,
) -> Any:
    """
    >>> from dataclasses import make_dataclass

    >>> cls = make_dataclass('cls', [('prop_1', str)])
    >>> type_hints = get_type_hints(cls, localns=locals())
    >>> _get_field_type(type_hints, 'prop_1')
    <class 'str'>

    >>> cls = make_dataclass('cls', [('prop_1', str | None)])
    >>> type_hints = get_type_hints(cls, localns=locals())
    >>> _get_field_type(type_hints, 'prop_1')
    <class 'str'>

    >>> cls = make_dataclass('cls', [('prop_1', list[int])])
    >>> type_hints = get_type_hints(cls, localns=locals())
    >>> _get_field_type(type_hints, 'prop_1')
    <class 'int'>

    >>> cls = make_dataclass('cls', [('prop_1', list[int | None])])
    >>> type_hints = get_type_hints(cls, localns=locals())
    >>> _get_field_type(type_hints, 'prop_1')
    <class 'int'>
    """  # noqa: E501 # pylint: disable=line-too-long
    if field_type := type_hints.get(field_name):
        return _get_real_type(field_type)


def _get_real_type(field_type: Any) -> Any:
    origin = get_origin(field_type)
    args: Sequence[type] = get_args(field_type)

    if origin and args:
        if origin is Union or origin is UnionType:
            no_optional = [a for a in args if a is not type(None)]  # noqa:E721
            if len(no_optional) == 1:
                return no_optional[0]
        elif issubclass(origin, Sequence):
            if len(args) == 1:
                return _get_real_type(args[0])

    return field_type


def _get_jfield_options(_field: Field[Any]):
    if options := _field.metadata.get(JFIELD_OPTIONS):
        return options

    return JFieldOptions(_field.name)
