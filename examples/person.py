from dataclasses import dataclass, field

from jdataclass import jfield


@dataclass
class Person:
    first_name: str = jfield(path="firstName")
    last_name: str = jfield(path="lastName")
    age: int = field(default=0)
