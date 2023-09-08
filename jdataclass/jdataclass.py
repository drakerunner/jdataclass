"""Custom dataclass serialization/deserialization.

jdataclass is a Python module that extends the functionality
of Python's native dataclasses by allowing custom mappings
for reading from dataclass objects and writing to other objects
during serialization and deserialization. With jdataclass, you
can easily control how data is mapped between your dataclass
and external data sources like JSON, databases, or other data
formats.

Typical usage:

    from dataclasses import dataclass, field
    from jdataclass import asdict, jfield

    @dataclass
    class Person:
        first_name: str = jfield(path="firstName")
        last_name: str = jfield(path="lastName")
        age: int = field(default=0)

    person = Person(first_name="John", last_name="Doe", age=30)
    asdict(person)  # Serialize Person to JSON
    {'firstName': 'John', 'lastName': 'Doe', 'age': 30}
"""  # noqa: E501 # pylint: disable=line-too-long
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods

import sys
from collections import ChainMap, UserDict
from dataclasses import _MISSING_TYPE  # type:ignore
from dataclasses import MISSING, Field, dataclass, field, fields, is_dataclass
from importlib import import_module
from inspect import isclass
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    SupportsIndex,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

if sys.version_info < (3, 10):
    from typing_extensions import ParamSpec
else:
    from types import UnionType
    from typing import ParamSpec

# constants:
_JFIELD_OPTIONS = "___JFIELD__options"
_JFIELDS = "__jfields__"
_JPROPERTIES = "__jproperties__"
_DATACLASS_POST_INIT_FN = "__post_init__"
_POST_ASDICT_NAME = "__post_asdict__"

#  TypeVars:
T = TypeVar("T")
P = ParamSpec("P")

_Key = TypeVar("_Key")
_Value = TypeVar("_Value")
_Item = TypeVar("_Item")
_Field = TypeVar("_Field")
_Transformed = TypeVar("_Transformed")

# types:
JSON = Mapping[str, "_JSON_DATA_TYPES"]
# pylint: disable-next=invalid-name
_JSON_DATA_TYPES = Union[
    str,
    int,
    float,
    complex,
    bool,
    None,
    Sequence["_JSON_DATA_TYPES"],
    Mapping[str, "_JSON_DATA_TYPES"],
]
# pylint: disable-next=invalid-name
_RECURSIVE_ARRAY = Union[_Transformed, list["_RECURSIVE_ARRAY"]]

# pylint: disable-next=invalid-name
_JPROPERTY_INITIALIZER = Callable[..., Union[JSON, Sequence[JSON]]]

# pylint: disable-next=invalid-name
_JPATH_TOKEN = tuple[str, Optional[_JPROPERTY_INITIALIZER]]


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
        path: Optional[str] = None,
        field_type: Optional[type] = None,
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


def jfield(
    *,
    path: Union[str, _MISSING_TYPE] = MISSING,
    parent_ref: Union[bool, _MISSING_TYPE] = MISSING,
    default: Union[T, _MISSING_TYPE] = MISSING,
    default_factory: Union[Callable[[], T], _MISSING_TYPE] = MISSING,
    init: bool = True,  # pylint:disable=w0621
    repr: bool = True,  # pylint:disable=redefined-builtin
    hash: Optional[bool] = None,  # pylint:disable=redefined-builtin
    compare: bool = True,
    metadata: Optional[Mapping[Any, Any]] = None,
    kw_only: Union[bool, _MISSING_TYPE] = MISSING,
) -> T:
    """Wrapper on top of field function add jfield options to metadata

    Args:
        path (str, optional): path in dictionary to get or set values when dsserializing or serializing.\n
        parent_ref (bool, optional): If true, when creating an instance of the object, this property will be set with a reference to an object that represents the parent in the deserialization hierarchy. See examples for more info. Defaults to False.\n
        default (T, optional): If provided, this will be the default value for this field. This is needed because the field() call itself replaces the normal position of the default value.\n
        default_factory (Callable[[], T], optional): If provided, it must be a zero-argument callable that will be called when a default value is needed for this field. Among other purposes, this can be used to specify fields with mutable default values, as discussed below. It is an error to specify both default and default_factory.\n
        init (bool, optional): If true (the default), this field is included as a parameter to the generated __init__() method\n
        repr (bool, optional): If true (the default), this field is included in the string returned by the generated __repr__() method.\n
        hash (bool, optional): This can be a bool or None. If true, this field is included in the generated __hash__() method. If None (the default), use the value of compare: this would normally be the expected behavior. A field should be considered in the hash if it’s used for comparisons. Setting this value to anything other than None is discouraged.\n
        compare (bool, optional): If true (the default), this field is included in the generated equality and comparison methods (__eq__(), __gt__(), et al.).\n
        metadata (Mapping[Any, Any] | None, optional): This can be a mapping or None. None is treated as an empty dict. This value is wrapped in MappingProxyType() to make it read-only, and exposed on the Field object. It is not used at all by Data Classes, and is provided as a third-party extension mechanism. Multiple third-parties can each have their own key, to use as a namespace in the metadata.\n
        kw_only (bool | _MISSING_TYPE, optional): If true, this field will be marked as keyword-only. This is used when the generated __init__() method’s parameters are computed.\n

    Returns:
        T: dataclass field with jfield options in metadata.
    """  # noqa: E501 # pylint: disable=line-too-long
    if metadata is None:
        metadata = {}

    path = path if path != MISSING else ""
    parent_ref = parent_ref if parent_ref != MISSING else False
    options = JFieldOptions(path, parent_ref)

    metadata |= {_JFIELD_OPTIONS: options}

    kw_args: Any = {
        "default": default,
        "default_factory": default_factory,  # type:ignore
        "init": init,
        "repr": repr,
        "hash": hash,
        "compare": compare,
        "metadata": metadata,
    }
    if sys.version_info >= (3, 10):
        kw_args["kw_only"] = kw_only

    return cast(T, field(**kw_args))


def jfields(class_or_instance: Union[T, type[T]]) -> tuple[JField, ...]:
    """Return a tuple describing the jfields of this dataclass

    Args:
        class_or_instance (T | type[T]):

    Returns:
        tuple[JField, ...]: jfields of this dataclass

    Examples:
        Setup:

        >>> from dataclasses import dataclass
        ...
        >>> @dataclass
        ... class MyClass:
        ...     prop_1: str
        ...     prop_2: list[str]
        ...     prop_3: Optional[str]
        ...
        >>> @dataclass
        ... class Child:
        ...     name: str
        ...
        >>> @dataclass
        ... class Parent:
        ...     name: str
        ...     children: list[Child]

        Get jfields from MyClass:

        >>> jfields(MyClass)
        (JField(name='prop_1', path='prop_1', field_type='str'), JField(name='prop_2', path='prop_2', field_type='str'), JField(name='prop_3', path='prop_3', field_type='str'))

        >>> _jfields = jfields(Parent)
        >>> _jfields
        (JField(name='name', path='name', field_type='str'), JField(name='children', path='children', field_type='Child'))
    """  # noqa: E501 # pylint: disable=line-too-long
    cls = (
        class_or_instance
        if isclass(class_or_instance)
        else type(class_or_instance)
    )

    if _jfields := getattr(cls, str(_JFIELDS), None):
        return cast(tuple[JField, ...], _jfields)

    _jfields = tuple(_build_jfields(cls))
    setattr(cls, str(_JFIELDS), _jfields)
    return _jfields


def _build_jfields(cls: type) -> Iterable[JField]:
    type_hints = _get_type_hints_with_module_refs(cls)
    for _field in fields(cls):
        options = _get_jfield_options(_field)

        if not _field.init:
            continue

        yield JField(
            name=_field.name,
            path=options.path,
            field_type=type_hints.get(_field.name),
            parent_ref=options.parent_ref,
        )


def _get_jfield_options(_field: Field[Any]) -> JFieldOptions:
    if options := _field.metadata.get(_JFIELD_OPTIONS):
        return cast(JFieldOptions, options)

    return JFieldOptions(_field.name)


class JProperty(Generic[T], property):
    """Descriptor encapsulating a property.

    It registers itself in the class __jproperties__ attribute.

    Args:
        Generic (T): property type
        property:
    """

    def __init__(
        self,
        fget: Callable[P, T],
        fset: Union[Callable[[Any, T], None], None],
        path: Union[str, None],
    ) -> None:
        super().__init__(fget=cast(Any, fget), fset=fset)
        self.owner: Any = None
        self.name = ""
        self.path = path

    def __set_name__(self, owner: Any, name: str) -> None:
        self.owner = owner
        self.name = name
        cls = owner if isclass(owner) else type(owner)

        _jproperties: tuple[_Lazy[JField], ...] = getattr(
            cls,
            _JPROPERTIES,
            tuple[_Lazy[JField], ...](),
        )
        _jproperties = _jproperties + (_Lazy(self._asfield),)

        setattr(owner, _JPROPERTIES, _jproperties)

    def _asfield(self) -> JField:
        type_hints = _get_type_hints_with_module_refs(self.fget)
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

    def setter(self, fset: Callable[[Any, T], None]) -> "JProperty[T]":
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
    fset: Optional[Callable[[Any, T], None]] = None,
    path: Optional[str] = None,
) -> Callable[[Callable[P, T]], JProperty[T]]:  # pragma: no cover
    ...


def jproperty(
    fget: Optional[Callable[P, T]] = None,
    *,
    fset: Optional[Callable[[Any, T], None]] = None,
    path: Optional[str] = None,
) -> Union[JProperty[T], Callable[[Callable[P, T]], JProperty[T]]]:
    """Decorator that creates a property bound to a jfield."""

    def wrap(fget: Callable[P, T]) -> JProperty[T]:
        return JProperty[T](fget, fset, path)

    if fget is None:
        return wrap

    return wrap(fget)


def jproperties(class_or_instance: Union[T, type[T]]) -> tuple[JField, ...]:
    """Return a tuple describing the jproperties of this dataclass

    Args:
        class_or_instance (T | type[T]):

    Returns:
        tuple[JField, ...]:

    Examples:
        Setup:

        >>> from dataclasses import dataclass
        ...
        >>> @dataclass
        ... class User:
        ...     first_name: str
        ...     last_name: str
        ...
        ...     @jproperty
        ...     def full_name(self) -> str:
        ...         return f"{self.first_name} {self.last_name}"

        >>> jproperties(User)
        (JField(name='full_name', path='full_name', field_type='str'),)

        Throws error if jproperty has no return type

        >>> @dataclass
        ... class WrongProperty:
        ...
        ...     @jproperty(path="name")
        ...     def name(self):
        ...         return "Guilherme"

        >>> jproperties(WrongProperty)
        Traceback (most recent call last):
        ...
        ValueError: JProperty must have a return type: WrongProperty.name

    """
    cls = (
        class_or_instance
        if isclass(class_or_instance)
        else type(class_or_instance)
    )
    _jproperties: Optional[tuple[_Lazy[JField]]]
    if _jproperties := getattr(cls, _JPROPERTIES, None):
        return tuple(j.value() for j in _jproperties)

    return tuple()


class _Lazy(Generic[_Value]):
    def __init__(self, factory: Callable[[], _Value]):
        self.factory = factory
        self._value: Optional[_Value] = None

    def value(self) -> _Value:
        """Return initialized value."""
        if self._value is None:
            self._value = self.factory()

        return self._value


def convert(
    source: Any,
    target_type: type[T],
    fields_to_copy: Optional[tuple[str, ...]] = None,
    memo: Optional[dict[int, Any]] = None,
) -> T:
    """Convert a jdataclass to another jdataclass

    It ignores any properties from the given instance that are not in
    the target type or in the given fields_to_copy parameter

    Args:
        instance (Any): source.\n
        target_type (type[T]): target type to be created.\n
        fields_to_copy (Optional[tuple[str, ...]], optional): filtered list of fields to be copied. Defaults to None. \n
        memo (Optional[dict[int, Any]], optional): memoization dict. Defaults to None. \n

    Returns:
        T: new instance of target type

    Examples:
        Setup:

        >>> @dataclass
        ... class Directory:
        ...     name: str
        ...     parent: Optional["Directory"] = field(default=None)
        ...     children: list["Directory"] = field(default_factory=list)
        ...
        >>> @dataclass
        ... class Folder:
        ...     name: str
        ...     parent: Optional["Folder"] = field(default=None)
        ...     children: list["Folder"] = field(default_factory=list)
        ...
        >>> mod = import_module(Directory.__module__)
        >>> setattr(mod, Directory.__name__, Directory)
        >>> setattr(mod, Folder.__name__, Folder)

        >>> parent = Directory("root")
        >>> child = Directory("home", parent)
        >>> parent.children.append(child)
        >>> convert(parent, Folder)
        Folder(name='root', parent=None, children=[Folder(name='home', parent=..., children=[])])
    """  # noqa: E501 # pylint: disable=line-too-long

    if memo is None:
        memo = {}

    memo_key = id(source)
    if memo_key in memo:
        return memo[memo_key]

    target = object.__new__(target_type)
    memo[memo_key] = target

    _jfields = tuple(
        f
        for f in jfields(target_type)
        if fields_to_copy is None or f.name in fields_to_copy
    )

    data = {
        _jfield.name: _transform_field(
            field_value=getattr(source, _jfield.name),
            field_type=_jfield.field_type,
            transformer=lambda v, t: convert(v, t, memo=memo),
        )
        for _jfield in _jfields  #
        if hasattr(source, _jfield.name)  #
    }

    if init_fn := getattr(target, "__init__"):
        init_fn(**data)

    return target


def create(
    cls: type[T],
    data: JSON,
    parent: Any = None,
    init_fn: Optional[Callable[[JSON, Any, T, Callable[..., T]], None]] = None,
) -> T:
    """Create an instnace of the given type and initilizes it with given data.

    Args:
        cls (type[T]): type to create and isntance from.\n
        data (JSON): data to fill the new instance with.\n
        parent (Any): used for fields with parent_ref enabled.\n
        init_fn (Optional[Callable[[JSON, Any, T, Callable[..., T]], None]], optional): init function. Defaults to None.\n

    Returns:
        T: initialized instance.

    Examples:
        Setup:

        >>> @dataclass
        ... class Directory:
        ...     name: str
        ...     files: list["File"] = field(default_factory=list)
        ...
        >>> @dataclass
        ... class File:
        ...     name: str
        ...     directory: "Directory" = jfield(parent_ref=True)
        ...
        >>> mod = import_module(Directory.__module__)
        >>> setattr(mod, Directory.__name__, Directory)
        >>> setattr(mod, File.__name__, File)

        >>> data = {
        ...     "name": "home",
        ...     "files": [
        ...         {"name": ".bashrc"},
        ...         {"name": ".profile"}
        ...     ]
        ... }
        >>> create(cls=Directory, data=data)
        Directory(name='home', files=[File(name='.bashrc', directory=...), File(name='.profile', directory=...)])
    """  # noqa: E501 # pylint: disable=line-too-long
    if init_fn is None:
        init_fn = _init

    instance = object.__new__(cls)
    init_fn(
        data,
        parent,
        instance,
        getattr(instance, "__init__"),
    )
    return instance


def _init(
    data: JSON,
    parent: Any,
    instance: T,
    init_fn: Callable[..., T],
) -> None:
    """Initialize the given instance with the given init_fn.

    The given init_fn will be called with the values of the
    instance jfields.

    After that the jproperty setters will be called using the
    values retrieved for jproperties paths.

    Args:
        data (JSON): object containing the source data. \n
        parent (Any): reference to be used by parent_ref fields. \n
        instance (Any): instance being initialized. It will be used as parent for nested references. \n
        init_fn (Callable[..., T]): init function to be called with jfields values

    Examples:
        Setup:

        >>> @dataclass
        ... class User:
        ...     first_name: str
        ...     _last_name: Optional[str] = field(init=False, default=None)
        ...
        ...     @jproperty
        ...     def last_name(self) -> str:
        ...         return self._last_name
        ...
        ...     @last_name.setter
        ...     def last_name(self, value:str) -> str:
        ...         self._last_name = value

        >>> data = {"first_name": "Guilherme", "last_name": "Vidal"}
        >>> instance = object.__new__(User)
        >>> _init(data, None, instance, getattr(instance, "__init__"))
        >>> instance
        User(first_name='Guilherme', _last_name='Vidal')
    """  # noqa: E501 # pylint: disable=line-too-long
    post_init_fn = None
    if hasattr(instance, _DATACLASS_POST_INIT_FN):
        post_init_fn = getattr(instance, _DATACLASS_POST_INIT_FN)

    def __post_init__(*args: Any, **kw_args: Any) -> None:
        cls = type(instance)
        for name, value in _get_data_values(
            data,
            parent,
            instance,
            jproperties(instance),
        ):
            if (prop := getattr(cls, name)) and prop.fset:
                setattr(instance, name, value)

        if post_init_fn:
            post_init_fn(*args, **kw_args)

    setattr(instance, _DATACLASS_POST_INIT_FN, __post_init__)

    init_fn(
        **dict(
            _get_data_values(
                data,
                parent,
                instance,
                jfields(instance),
            )
        )
    )

    if post_init_fn:
        setattr(instance, _DATACLASS_POST_INIT_FN, post_init_fn)
    else:
        __post_init__(instance)
        delattr(instance, _DATACLASS_POST_INIT_FN)


def _get_data_values(
    data: JSON,
    parent: Any,
    instance: Any,
    _jfields: tuple[JField, ...],
) -> Iterable[tuple[str, Any]]:
    """Get values from given data using given jfields:

    Args:
        data (JSON): object containing the source data. \n
        parent (Any): reference to be used by parent_ref fields. \n
        instance (Any): instance being initialized. It will be used
        as parent for nested references. \n
        _jfields (tuple[JField, ...]): will only get values for these
        given jfields.

    Returns:
        Iterable[tuple[str, Any]]: field name and value (name, value)

    Yields:
        Iterator[Iterable[tuple[str, Any]]]:

    Examples:
        Setup:

        >>> @dataclass
        ... class User:
        ...     first_name: str
        ...     last_name: str

        >>> data = {"first_name": "Guilherme", "last_name": "Vidal"}
        >>> instance = object.__new__(User)
        >>> list(_get_data_values(data, None, instance, jfields(instance)))
        [('first_name', 'Guilherme'), ('last_name', 'Vidal')]
    """
    for _jfield in _jfields:
        value: Any = None
        if _jfield.parent_ref:
            value = parent
        else:
            value = _transform_field(
                field_value=_get_dict_value(data, _jfield.path),
                field_type=_jfield.field_type,
                transformer=lambda v, t: create(
                    cls=t,
                    data=v,
                    parent=instance,
                ),
            )

        yield (_jfield.name, value)


def asdict(instance: Any) -> JSON:
    """Convert instance to a dictionary using the defined
    jfields paths.

    Args:
        instance (Any): instance of a dataclass to be
        converted to a JSON

    Returns:
        JSON:

    Examples:
        Setup:

        >>> @dataclass
        ... class User:
        ...     first_name: str
        ...     last_name: str
        ...
        ...     @jproperty
        ...     def full_name(self) -> str:
        ...         return f"{self.first_name} {self.last_name}"
        ...
        ...     def __post_asdict__(self, data: JSON):
        ...         data["post_init"] = True
        ...         return data

        >>> data = _defaultdict()
        >>> instance = User("Guilherme", "Vidal")
        >>> asdict(instance)
        {'first_name': 'Guilherme', 'last_name': 'Vidal', 'full_name': 'Guilherme Vidal', 'post_init': True}
    """  # noqa: E501 # pylint: disable=line-too-long

    json: JSON = _defaultdict()

    _set_data_values(json, instance, jfields(instance))
    _set_data_values(json, instance, jproperties(instance))

    if hasattr(instance, _POST_ASDICT_NAME):
        json = getattr(instance, _POST_ASDICT_NAME)(json)

    return json


def _set_data_values(
    data: "_defaultdict[str, Any]",
    instance: Any,
    _jfields: tuple[JField, ...],
):
    """Set values on given data using given jfields:

    Args:
        data (_defaultdict[str, Any]): object to get populated
        with values from instance.

        instance (Any): source for data values\n
        _jfields (tuple[JField, ...]): will only get values for these
        given jfields.

    Examples:
        Setup:

        >>> @dataclass
        ... class User:
        ...     first_name: str
        ...     last_name: str

        >>> data = _defaultdict()
        >>> instance = User("Guilherme", "Vidal")
        >>> _set_data_values(data, instance, jfields(instance))
        >>> data
        {'first_name': 'Guilherme', 'last_name': 'Vidal'}
    """
    for _jfield in _jfields:
        if not _jfield.parent_ref:
            value = _transform_field(
                field_value=getattr(instance, _jfield.name),
                field_type=_jfield.field_type,
                transformer=lambda v, t: asdict(v),
            )
            _set_dict_value(data, _jfield.path, value)


def _transform_field(
    *,
    field_value: Union[_Field, _Transformed],
    field_type: Optional[type[_Transformed]],
    transformer: Callable[[_Field, type], _Transformed],
) -> _RECURSIVE_ARRAY[_Transformed]:
    """Applies a transformer functions to values from a dataclass.

    If the given type is a dataclass, the given transformer function
    will be called for each item in the given value.

    Otherwise the given value will be returned with no transformations
    applied

    Args:
        field_value (T): value to be transformed \n
        field_type (Optional[type[W]]): type of the given value \n
        transformer (Callable[[T, type], W]): function to be called
        with each item from value.

    Returns:
        W: transformed value or the given value if the given type is
        not a dataclass

    Examples:
        Setup

        >>> from dataclasses import dataclass
        ...
        >>> @dataclass
        ... class User:
        ...     first_name: str
        ...
        >>> def transform_fn(first_name: Any, type: Any):
        ...     return User(first_name)

        Transform a single dataclass

        >>> _transform_field(
        ...     field_value="Guilherme",
        ...     field_type=User,
        ...     transformer=transform_fn
        ... )
        User(first_name='Guilherme')

        Transform a list of dataclasses

        >>> _transform_field(
        ...     field_value=["Guilherme"],
        ...     field_type=User,
        ...     transformer=transform_fn
        ... )
        [User(first_name='Guilherme')]

        Transform nested arrays

        >>> _transform_field(
        ...     field_value=[["Guilherme"]],
        ...     field_type=User,
        ...     transformer=transform_fn
        ... )
        [[User(first_name='Guilherme')]]

        Transform not a dataclass

        >>> _transform_field(
        ...     field_value="Guilherme",
        ...     field_type=str,
        ...     transformer=transform_fn
        ... )
        'Guilherme'
    """
    if field_value and field_type and is_dataclass(field_type):
        field_value = cast(_Field, field_value)
        [field_value] = _recurse_nested_sequences(
            [field_value],
            field_type,
            transformer,
        )

        return field_value

    field_value = cast(_Transformed, field_value)
    return field_value


def _recurse_nested_sequences(
    values: Sequence[_Field],
    field_type: type[_Transformed],
    transformer: Callable[[_Field, type], _Transformed],
) -> Iterable[_Transformed]:
    for value in values:
        if isinstance(value, Sequence) and not isinstance(value, str):
            nested_values: Sequence[_Field] = value
            transformed_values: Any = list(
                _recurse_nested_sequences(
                    nested_values,
                    field_type,
                    transformer,
                )
            )

            yield transformed_values
        else:
            yield transformer(value, field_type)


def _get_dict_value(obj: JSON, path: str) -> Any:
    """Get a value from a given dict following the given path.

    The given path is tokenized and each token is used to navigate
    through the given dict. When the path is fully navigated, the
    value is returned.

    If the path is not fully navigated, None is returned.

    Args:
        obj (JSON): \n
        path (str):

    Returns:
        Any: propety value

    Examples:

        >>> obj = {
        ...    "users":[{
        ...         "first_name": "Guilherme",
        ...         "last_name": "Vidal"
        ...     }]
        ... }

        >>> _get_dict_value(obj, "users.0.first_name")
        'Guilherme'
    """
    current: Any = obj
    for property_name, _ in _tokenize_path(path):
        if property_name.isnumeric():
            property_name = int(property_name)

        try:
            current = current[property_name]
        except (KeyError, IndexError):
            return None

    return current


def _set_dict_value(
    obj: "_defaultdict[str, Any]",
    path: str,
    value: Any,
) -> None:
    """Set a value of a given dict following the given path.

    The given path is tokenized and each token is used to navigate
    through the given dict. When the path is fully navigated, the
    value is set.

    Args:
        obj (_defaultdict[str, Any]): must be a _defaultdict to avoid
        problems accessing properties that are not yet initialized.

        path (str): \n
        value (Any): \n

    Examples:

        >>> obj = _defaultdict()
        >>> _set_dict_value(obj, "users.0.first_name", "Guilherme")
        >>> obj
        {'users': [{'first_name': 'Guilherme'}]}
    """
    current: Any = obj
    for property_name, initializer in _tokenize_path(path):
        if property_name.isnumeric():
            property_name = int(property_name)

        if not callable(initializer):
            current[property_name] = value
        elif current[property_name] is None:
            current[property_name] = initializer()

        current = current[property_name]


def _tokenize_path(path: str) -> Iterable[_JPATH_TOKEN]:
    """Return tokens that represent the given path.

    Each token is a tuple with a property name
    and a factory function that creates the next object
    in the given path.

    If the a path is represented by "a.b" it means that
    "b" is a property in a nested dict represented by the
    property "a".

    So when navigating the tokens, if property "a" is None
    we need to create it with the token's factory

    Args:
        path (str): path to tokenize.
        Represents a path inside a JSON object.

    Returns:
        Iterable[JPATH_TOKEN]:

    Yields:
        Iterator[Iterable[JPATH_TOKEN]]:

    Examples:
        Setup:

        >>> def _nomalize_initializers_class_names(tokens):
        ...     for (prop, initializer) in tokens:
        ...         if initializer is None:
        ...             yield (prop, None)
        ...         else:
        ...             yield (prop, initializer.__name__)

        >>> tokens = _tokenize_path("addresses.0.address_1")
        >>> tuple(_nomalize_initializers_class_names(tokens))
        (('addresses', '_defaultlist'), ('0', '_defaultdict'), ('address_1', None))
    """  # noqa: E501 # pylint: disable=line-too-long
    previous: Optional[str] = None
    for token in path.split("."):
        if previous is None:
            previous = token
            continue

        yield (previous, _get_token_factory(token))
        previous = token

    if previous:
        yield (previous, None)


def _get_token_factory(
    path_token: str,
) -> _JPROPERTY_INITIALIZER:
    """Return an initializer for given token.

    Args:
        path_token (str): single jpath token from a path.

    Returns:
        _JPROPERTY_INITIALIZER: defaultlist for numeric tokens,
        defaultdict otherwise.

    Returns list for numeric path.

    >>> _get_token_factory("1").__name__
    '_defaultlist'

    Returns dict for others.

    >>> _get_token_factory("name").__name__
    '_defaultdict'
    """
    if path_token.isnumeric():
        return cast(_JPROPERTY_INITIALIZER, _defaultlist)

    return cast(_JPROPERTY_INITIALIZER, _defaultdict)


class _defaultlist(list[_Item], Generic[_Item]):
    """List that resizes itself when an index out of range is accessed.

    Set value at index out of range

    >>> l = _defaultlist()
    >>> l[1] = 1
    >>> l
    [None, 1]

    Get value from index out of range

    >>> l = _defaultlist()
    >>> l[1]

    """

    def __init__(
        self,
        default_factory: Optional[Callable[[], _Item]] = None,
    ) -> None:
        self.default_factory = default_factory or (lambda: None)

    @overload
    def __getitem__(self, __i: SupportsIndex) -> _Item:  # pragma: no cover
        ...

    @overload
    def __getitem__(self, __s: slice) -> list[_Item]:  # pragma: no cover
        ...

    def __getitem__(self, key: Any) -> Any:
        self.__ensure_length(key + 1)

        return cast(Any, super().__getitem__(key))

    @overload
    def __setitem__(
        self, key: SupportsIndex, value: _Item
    ) -> None:  # pragma: no cover
        ...

    @overload
    def __setitem__(
        self, key: slice, value: Iterable[_Item]
    ) -> None:  # pragma: no cover
        ...

    def __setitem__(self, key: Any, value: Any):
        self.__ensure_length(key + 1)

        super().__setitem__(key, value)

    def __ensure_length(self, max_length: int):
        if len(self) < max_length:
            self += [self.default_factory()] * (max_length - len(self))


class _defaultdict(dict[_Key, _Value], Generic[_Key, _Value]):
    """defaultdict for JSON build.

    Return None when property not in dict

    >>> d = _defaultdict()
    >>> d["my-prop"]
    """

    def __missing__(self, key: _Key):
        return None


def _get_type_hints_with_module_refs(obj: Any) -> "_TypeHints":
    """Get type hints including obj module in localns.

    Internally get_type_hints() is called with localns set to the
    module of obj to resolve forward references.

    Args:
        obj (Any): may be a module, class, method, function.

    Returns:
        _TypeHints:

    Examples:
        Setup:

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
        >>> mod = import_module(_get_type_hints_with_module_refs.__module__)
        >>> setattr(mod, Owner.__name__, Owner)
        >>> setattr(mod, Pet.__name__, Pet)

        Get type hints for Owner class:

        >>> { k: v.__name__
        ...     for k, v
        ...     in _get_type_hints_with_module_refs(Owner).items()
        ... }
        {'name': 'str', 'pet': 'Pet'}

        Get type hints for create_pet function:

        >>> { k: v.__name__
        ...     for k, v
        ...     in _get_type_hints_with_module_refs(create_pet).items()
        ... }
        {'name': 'str', 'return': 'Pet'}
    """
    localns = locals()
    if obj.__module__:
        localns = cast(
            dict[str, Any],
            ChainMap(vars(import_module(obj.__module__)), localns),
        )

    return _TypeHints(
        get_type_hints(
            obj,
            localns=localns,
        ),
        localns,
    )


class _TypeHints(UserDict[str, type]):
    def __init__(self, data: dict[str, type], localns: dict[str, type]):
        super().__init__(data)
        self.localns = localns

    def __getitem__(self, key: str) -> type:
        return self._get_real_type(super().__getitem__(key))

    def _get_real_type(self, field_type: Any) -> Any:
        origin = get_origin(field_type)
        args: Sequence[type] = get_args(field_type)

        if origin and args:
            if _is_union_type(origin):
                no_optional = [
                    a for a in args if a is not type(None)  # noqa:E721
                ]
                if len(no_optional) == 1:
                    return no_optional[0]
            elif issubclass(origin, Sequence):
                if len(args) == 1:
                    return self._get_real_type(args[0])

        if isinstance(field_type, str):
            return self.localns.get(field_type, field_type)

        return field_type


def _is_union_type(origin: Any):
    if sys.version_info < (3, 10):
        return origin is Union

    return origin is Union or origin is UnionType


if __name__ == "__main__":
    import doctest

    doctest.testmod()
