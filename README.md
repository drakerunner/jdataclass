# jdataclass — Custom dataclass Serialization/Deserialization

jdataclass is a Python module that extends the functionality of Python's native dataclasses by allowing custom mappings for reading from dataclass objects and writing to other objects during serialization and deserialization. With jdataclass, you can easily control how data is mapped between your dataclass and external data sources like JSON, databases, or other data formats.

## Install the package

You can install jdataclass using pip:

```bash
pip install jdataclass
```

## Usage

Here's a guide on how to use jdataclass in your Python projects.

### Defining a Dataclass

Create a dataclass as you normally would, and use jfield and jproperty annotations to specify custom mappings for your fields and properties.

```python
from dataclasses import dataclass, field
from jdataclass import jfield

@dataclass
class Person:
    first_name: str = jfield(path="firstName")
    last_name: str = jfield(path="lastName")
    age: int = field(default=0)
```
<!--
>>> from examples.person import Person

-->
In the example above, we have defined a dataclass, `Person`. This dataclass uses `jfield` annotations to specify custom field mappings.

### Serialization and Deserialization

You can now serialize and deserialize your dataclasses using jdataclass:


#### Serialization (to JSON)

```python
>>> from jdataclass import asdict

>>> person = Person(first_name="John", last_name="Doe", age=30)
>>> asdict(person)  # Serialize Person to JSON
{'firstName': 'John', 'lastName': 'Doe', 'age': 30}

```

#### Deserialization (from JSON)

```python
>>> from jdataclass import create

>>> json_data = {
...    "firstName": "Jane",
...    "lastName": "Doe",
...    "age": 25
... }

>>> create(Person, json_data)  # Deserialize JSON to Person
Person(first_name='Jane', last_name='Doe', age=25)

```

## Module contents

jdataclass provides several functions to work with custom mappings and dataclass objects:

- `JField`: Holds options for a field, used during serialization and deserialization.
- `JFieldOptions`: dataclass that is added to a field metadata and is used to create a `JField`.
- `JProperty`: A descriptor that replaces the getters and setters for a jproperty.
- `jfield`: Factory function to create a Field with the metadata that JField needs.
- `jfields`: Function that returns all jfields defined of a given class.
- `jproperty`: A decorator to specify custom property mappings for a dataclass property.
- `jproperties`: A function that returns all jproperties of a given class.
- `create`: Create a dataclass object from a dictionary of data using custom mappings.
- `asdict`: Serialize a dataclass object to a dictionary using custom mappings.
- `convert`: Converts one dataclass to another.

## Examples

### jproperty

Sometimes we need to map the result of a function to a field in the serialized object or have custom functionality when deserializing a field. 

For these scenarios jproperties allow us to define read-only or read-write operations that happen during deserialization and/or serialization.

Consider the following JSON response from the `Purview Azure SDK`:
```JSON
{
    "friendlyName": "SubCollection",
    "name": "000001",
    "parentCollection": {
        "referenceName": "000000",
        "type": "CollectionReference"
    }
}
```

The property `parentCollection` contains the `name` of the parent collection and a `type` that is fixed to `CollectionReference`.

We can create a jdataclass that represents these mappings as follows:

```python
from dataclasses import dataclass
from jdataclass import jfield, jproperty
from typing import Any, Optional

@dataclass
class PurviewCollection:
    name: str
    friendly_name: str = jfield(path="friendlyName")

    parent_name: Optional[str] = jfield(
        path="parentCollection.referenceName",
        default=None,
    )

    @jproperty(path="parentCollection.type")
    def collection_reference(self):
        return "CollectionReference"

    ...

```
<!--
>>> from examples.purview_collection import PurviewCollection, PurviewResponse, LocalCollection

-->

#### Deserialization (from JSON)

```python
>>> from jdataclass import create

>>> json_data = {'name': '000001', 'friendlyName': 'SubCollection', 'parentCollection': {'referenceName': '000000', 'type': 'CollectionReference'}}
>>> create(PurviewCollection, json_data)  # Deserialize JSON to PurviewCollection
PurviewCollection(name='000001', friendly_name='SubCollection', parent_name='000000')

```
#### Serialization (to JSON)

```python
>>> from jdataclass import asdict

>>> collection = PurviewCollection(name='000001', friendly_name='SubCollection', parent_name='000000')
>>> asdict(collection)  # Serialize PurviewCollection to JSON
{'name': '000001', 'friendlyName': 'SubCollection', 'parentCollection': {'referenceName': '000000', 'type': 'CollectionReference'}}

```

### Post serialization (`__post_asdict__`)

Sometimes we need to interfere with the serialization process for custom post processing of the generated dict.

Considering the previous example, assume a collection that has no parent. We would like the generated JSON to drop the `parentCollection` property entirelly.
So, let's change the class a little and add a new method called `__post_asdict__`

```python
...

@dataclass
class PurviewCollection:
    ...

    def __post_asdict__(self, data: dict[str, Any]):
        if self.parent_name is None:
            del data["parentCollection"]

```

#### Serialization (to JSON)

```python
>>> from jdataclass import asdict

>>> collection = PurviewCollection(name='000000', friendly_name='Root', parent_name=None)
>>> asdict(collection)  # Serialize PurviewCollection to JSON
{'name': '000000', 'friendlyName': 'Root'}

```

`__post_asdict__` method is called just after all fields and properties have been initialized.

### Post deserialization (`__post_init__`)

The `dataclass` native `__post_init__` method can be used for post deserialization.

Consider the previous example, collections from the `Purview` api are returned with only the `referenceName` for the parent collection. Let's say we want to make the hierarchy explicit by combining collections by `parent_name`. We can accomplish this after serialization with somthing like the following:

##### Response from `list_collections`
```python
 json_data = {
    "value": [
        {
            "friendlyName": "Root",
            "name": "000000",
        },
        {
            "friendlyName": "SubCollection",
            "name": "000001",
            "parentCollection": {
                "referenceName": "000000",
                "type": "CollectionReference",
            },
        },
    ],
}
```
<!--
>>> json_data = {"value": [{"friendlyName": "Root", "name": "000000"}, { "friendlyName": "SubCollection", "name": "000001", "parentCollection": { "referenceName": "000000", "type": "CollectionReference"}}]}

-->

```python
...

@dataclass
class PurviewCollection:
    ...

    collections: list["PurviewCollection"] = jfield(
        init=False,
        default_factory=list,
    )

    parent: Optional["PurviewCollection"] = jfield(
        init=False,
        default=None,
    )

    ...

@dataclass
class PurviewResponse:
    root: Optional[PurviewCollection] = jfield(init=False)
    collections: list[PurviewCollection] = jfield(
        path="value",
        default_factory=list,
    )

    def __post_init__(self):
        by_name = {c.name: c for c in self.collections}

        for c in self.collections:
            if c.parent_name and (parent := by_name.get(c.parent_name)):
                c.parent = parent
                parent.collections.append(c)
            else:
                self.root = c
```

#### Deserialization (from JSON)

```python
>>> from jdataclass import create

>>> response = create(PurviewResponse, json_data)  # Deserialize JSON to PurviewResponse
>>> response.root
PurviewCollection(name='000000', friendly_name='Root', collections=[PurviewCollection(name='000001', friendly_name='SubCollection', parent_name='000000')], parent_name=None)

```

### Convert

Sometimes we need to convert a dataclass that maps an external api to an internal mapper to save the data in a different format.

Consider the previous example, now we would like to store the contents of a `PurviewCollection` as a different format like the following:

```python
@dataclass
class LocalCollection:
    name: str
    friendly_name: str = jfield(path="friendlyName")
    collections: list["LocalCollection"] = jfield(default_factory=list)

    parent: Optional["LocalCollection"] = jfield(
        parent_ref=True,
        default=None,
    )

    @property
    def parent_name(self) -> Optional[str]:
        return self.parent and self.parent.name
```

We can easily convert a `PurviewCollection` to such class by using the `convert` function. It will copy all fields defined in the `LocalCollection` from the given instance of `PurviewCollection`.

```python
>>> from jdataclass import convert

>>> response = create(PurviewResponse, json_data)  # Deserialize JSON to PurviewResponse
>>> collection = convert(response.root, LocalCollection)
>>> collection
LocalCollection(name='000000', friendly_name='Root', collections=[LocalCollection(name='000001', friendly_name='SubCollection', collections=[], parent=...)], parent=None)

>>> asdict(collection)
{'name': '000000', 'friendlyName': 'Root', 'collections': [{'name': '000001', 'friendlyName': 'SubCollection', 'collections': []}]}

```

## Contributions and Issues

If you encounter any issues, have questions, or want to contribute to jdataclass, please visit our [GitHub repository](https://github.com/drakerunner/jdataclass). We welcome your feedback and contributions.

## License

jdataclass is licensed under the MIT License. See the [LICENSE](https://github.com/drakerunner/jdataclass/LICENSE) file for more details.

---

Thank you for using jdataclass! We hope this library simplifies the process of custom data mappings for your dataclass objects.