from dataclasses import is_dataclass
from typing import Any, Callable, Iterable, Optional, Sequence, TypeVar

from jdataclass.constants import DATACLASS_POST_INIT_FN, POST_ASDICT_NAME
from jdataclass.defaultdict import defaultdict
from jdataclass.dict_utils import get_dict_value, set_dict_value
from jdataclass.jfield import JField, jfields
from jdataclass.jproperty import jproperties
from jdataclass.types import JSON

T = TypeVar("T")


def convert(
    source: Any,
    target_type: type[T],
    fields_to_copy: Optional[tuple[str, ...]] = None,
    memo: dict[int, Any] = dict(),
) -> T:
    """Convert a jdataclass to another jdataclass

    It ignores any properties from the given instance that are not in
    the target type or in the given fields_to_copy parameter

    Args:
        instance (Any): source.\n
        target_type (type[T]): target type to be created.\n
        fields_to_copy (Optional[tuple[str, ...]], optional):
        filtered list of fields to be copied. Defaults to None.

        memo (dict[int, Any], optional): memoized state to avoid
        problems with circular refs. Defaults to dict().

    Returns:
        T: new instance of target type


    >>> from dataclasses import dataclass, field
    >>> from importlib import import_module
    ...
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
    ...
    >>> parent = Directory("root")
    >>> child = Directory("home", parent)
    >>> parent.children.append(child)
    >>> convert(parent, Folder)
    Folder(name='root', parent=None, children=\
[Folder(name='home', parent=..., children=[])])
    """
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
        _jfield.name: transform_field(
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
        init_fn (Optional[Callable[[JSON, Any, T, Callable[..., T]], None]],
        optional): init function. Defaults to None.

    Returns:
        T: initialized instance.

    >>> from dataclasses import dataclass, field
    >>> from jdataclass.jfield import jfield
    >>> from importlib import import_module
    ...
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
    ...
    >>> data = {
    ...     "name": "home",
    ...     "files": [
    ...         {"name": ".bashrc"},
    ...         {"name": ".profile"}
    ...     ]
    ... }
    >>> create(cls=Directory, data=data)
    Directory(name='home', files=[File(name='.bashrc', directory=...), \
File(name='.profile', directory=...)])
    """
    if init_fn is None:
        init_fn = init

    instance = object.__new__(cls)
    init_fn(
        data,
        parent,
        instance,
        getattr(instance, "__init__"),
    )
    return instance


def init(
    data: JSON,
    parent: Any,
    instance: T,
    init_fn: Callable[..., T],
):
    """Initialize the given instance with the given init_fn.

    The given init_fn will be called with the values of the
    instance jfields.

    After that the jproperty setters will be called using the
    values retrieved for jproperties paths.

    Args:
        data (JSON): object containing the source data. \n
        parent (Any): reference to be used by parent_ref fields. \n
        instance (Any): instance being initialized. It will be used
        as parent for nested references. \n
        init_fn (Callable[..., T]): init function to be called with
        jfields values

    >>> from dataclasses import dataclass, field
    >>> from jdataclass.jproperty import jproperty

    >>> @dataclass
    ... class User:
    ...     first_name: str
    ...     _last_name: str | None = field(init=False, default=None)
    ...
    ...     @jproperty
    ...     def last_name(self) -> str:
    ...         return self._last_name
    ...
    ...     @last_name.setter
    ...     def last_name(self, value:str) -> str:
    ...         self._last_name = value
    ...
    >>> data = {"first_name": "Guilherme", "last_name": "Vidal"}
    >>> instance = object.__new__(User)
    >>> init(data, None, instance, getattr(instance, "__init__"))
    >>> instance
    User(first_name='Guilherme', _last_name='Vidal')
    """
    post_init_fn = None
    if hasattr(instance, DATACLASS_POST_INIT_FN):
        post_init_fn = getattr(instance, DATACLASS_POST_INIT_FN)

    def __post_init__(*args: Any, **kw_args: Any):
        kw = get_data_values(data, parent, instance, jproperties(instance))
        cls = type(instance)
        for name, value in kw:
            if (prop := getattr(cls, name)) and prop.fset:
                setattr(instance, name, value)

        if post_init_fn:
            post_init_fn(*args, **kw_args)

    setattr(instance, DATACLASS_POST_INIT_FN, __post_init__)

    kw = dict(get_data_values(data, parent, instance, jfields(instance)))
    init_fn(**kw)

    if post_init_fn:
        setattr(instance, DATACLASS_POST_INIT_FN, post_init_fn)
    else:
        __post_init__(instance)
        delattr(instance, DATACLASS_POST_INIT_FN)


def get_data_values(
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

    >>> from dataclasses import dataclass
    ...
    >>> @dataclass
    ... class User:
    ...     first_name: str
    ...     last_name: str
    ...
    >>> data = {"first_name": "Guilherme", "last_name": "Vidal"}
    >>> instance = object.__new__(User)
    >>> list(get_data_values(data, None, instance, jfields(instance)))
    [('first_name', 'Guilherme'), ('last_name', 'Vidal')]
    """
    for _jfield in _jfields:
        value: Any = None
        if _jfield.parent_ref:
            value = parent
        else:
            value = transform_field(
                field_value=get_dict_value(data, _jfield.path),
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
        instance (Any):

    Returns:
        JSON:


    >>> from dataclasses import dataclass
    >>> from jdataclass.jproperty import jproperty
    ...
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
    ...
    >>> data = defaultdict()
    >>> instance = User("Guilherme", "Vidal")
    >>> asdict(instance)
    {'first_name': 'Guilherme', 'last_name': 'Vidal', \
'full_name': 'Guilherme Vidal', 'post_init': True}
    """
    json: JSON = defaultdict()

    set_data_values(json, instance, jfields(instance))
    set_data_values(json, instance, jproperties(instance))

    if hasattr(instance, POST_ASDICT_NAME):
        getattr(instance, POST_ASDICT_NAME)(json)

    return json


def set_data_values(
    data: defaultdict[str, Any],
    instance: Any,
    _jfields: tuple[JField, ...],
):
    """Set values on given data using given jfields:

    Args:
        data (defaultdict[str, Any]): object to get populated
        with values from instance.

        instance (Any): source for data values\n
        _jfields (tuple[JField, ...]): will only get values for these
        given jfields.

    >>> from dataclasses import dataclass
    ...
    >>> @dataclass
    ... class User:
    ...     first_name: str
    ...     last_name: str
    ...
    >>> data = defaultdict()
    >>> instance = User("Guilherme", "Vidal")
    >>> set_data_values(data, instance, jfields(instance))
    >>> data
    {'first_name': 'Guilherme', 'last_name': 'Vidal'}
    """
    for _jfield in _jfields:
        if not _jfield.parent_ref:
            value = transform_field(
                field_value=getattr(instance, _jfield.name),
                field_type=_jfield.field_type,
                transformer=lambda v, t: asdict(v),
            )
            set_dict_value(data, _jfield.path, value)


def transform_field(
    *,
    field_value: T,
    field_type: Optional[type],
    transformer: Callable[[T, type], Any],
) -> Any:
    """Applies a transformer functions to values from a dataclass.

    If the given type is a dataclass, the given transformer function
    will be called for each item in the given value.

    Otherwise the given value will be returned with no transformations
    applied

    Args:
        field_value (T): value to be transformed \n
        field_type (Optional[type]): type of the given value \n
        transformer (Callable[[T, type], Any]): function to be called
        with each item from value.

    Returns:
        Any: transformed value or the given value if the given type is
        not a dataclass

    >>> from dataclasses import dataclass
    ...
    >>> @dataclass
    ... class User:
    ...     first_name: str
    ...
    >>> def transform_fn(first_name: Any, type: Any):
    ...     return User(first_name)

    Transform a single dataclass
    >>> transform_field(
    ...     field_value="Guilherme",
    ...     field_type=User,
    ...     transformer=transform_fn
    ... )
    User(first_name='Guilherme')

    Transform a list of dataclasses
    >>> transform_field(
    ...     field_value=["Guilherme"],
    ...     field_type=User,
    ...     transformer=transform_fn
    ... )
    [User(first_name='Guilherme')]

    Transform not a dataclass
    >>> transform_field(
    ...     field_value="Guilherme",
    ...     field_type=str,
    ...     transformer=transform_fn
    ... )
    'Guilherme'
    """
    if field_value and field_type and is_dataclass(field_type):
        if isinstance(field_value, Sequence) and not isinstance(
            field_value, str
        ):
            values: Sequence[Any] = field_value
            return [transformer(j, field_type) for j in values]

        return transformer(field_value, field_type)

    return field_value


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    doctest.testmod()
