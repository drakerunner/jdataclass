from typing import Any, Iterable, cast

from jdataclass.defaultdict import defaultdict
from jdataclass.defaultlist import defaultlist
from jdataclass.types import JPATH_TOKEN, JPROPERTY_INITIALIZER, JSON


def get_dict_value(obj: JSON, path: str) -> Any:
    """Get a value from a given dict following the given path

    Args:
        obj (JSON): \n
        path (str):

    Returns:
        Any: propety value

    >>> obj = {
    ...    "users":[{
    ...         "first_name": "Guilherme",
    ...         "last_name": "Vidal"
    ...     }]
    ... }

    >>> get_dict_value(obj, "users.0.first_name")
    'Guilherme'
    """
    current: Any = obj
    for property_name, _ in tokenize_path(path):
        if property_name.isdigit():
            property_name = int(property_name)

        try:
            current = current[property_name]
        except (KeyError, IndexError):
            return None

    return current


def set_dict_value(obj: defaultdict[str, Any], path: str, value: Any) -> None:
    """Set a value of a given dict following the given path

    Args:
        obj (defaultdict[str, Any]): must be a defaultdict to avoid problems
        accessing properties that are not yet initialized.

        path (str): \n
        value (Any): \n

    >>> obj = defaultdict()
    >>> set_dict_value(obj, "users.0.first_name", "Guilherme")
    >>> obj
    {'users': [{'first_name': 'Guilherme'}]}
    """  # noqa: E501 # pylint: disable=line-too-long
    current: Any = obj
    for property_name, initializer in tokenize_path(path):
        if property_name.isdigit():
            property_name = int(property_name)

        if not callable(initializer):
            current[property_name] = value
        elif current[property_name] is None:
            current[property_name] = initializer()

        current = current[property_name]


def tokenize_path(path: str) -> Iterable[JPATH_TOKEN]:
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
        path (str):

    Returns:
        Iterable[JPATH_TOKEN]:

    Yields:
        Iterator[Iterable[JPATH_TOKEN]]:

    >>> tuple(tokenize_path("addresses.0.address_1"))
    (('addresses', <class 'jdataclass.defaultlist.defaultlist'>), ('0', <class 'jdataclass.defaultdict.defaultdict'>), ('address_1', None))
    """  # noqa: E501 # pylint: disable=line-too-long
    previous: str | None = None
    for token in path.split("."):
        if previous is None:
            previous = token
            continue

        yield (previous, get_token_factory(token))
        previous = token

    if previous:
        yield (previous, None)


def get_token_factory(
    path_token: str,
) -> JPROPERTY_INITIALIZER | None:
    """Return a initializer for given token.

    Args:
        path_token (str):

    Returns list for ints.
    >>> get_token_factory("1")
    <class 'jdataclass.defaultlist.defaultlist'>

    Returns dict for others.
    >>> get_token_factory("name")
    <class 'jdataclass.defaultdict.defaultdict'>
    """
    if path_token.isdigit():
        return cast(JPROPERTY_INITIALIZER, defaultlist)

    return cast(JPROPERTY_INITIALIZER, defaultdict)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
