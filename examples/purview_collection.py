from dataclasses import dataclass
from typing import Any, Generic, Optional, Protocol, TypeVar

from jdataclass import jfield, jproperty

T = TypeVar("T", bound="Collection[Any]")  # type: ignore


class Collection(Generic[T], Protocol):
    name: str
    friendly_name: str
    collections: list[T]

    parent: Optional[T]
    parent_name: Optional[str]


@dataclass
class LocalCollection(Collection["LocalCollection"]):
    name: str
    friendly_name: str = jfield(path="friendlyName")
    collections: list["LocalCollection"] = jfield(default_factory=list)

    parent: Optional["LocalCollection"] = jfield(
        parent_ref=True,
        default=None,
    )

    @property
    def parent_name(self) -> Optional[str]:  # type:ignore
        return self.parent and self.parent.name


@dataclass
class PurviewCollection(Collection["PurviewCollection"]):
    name: str
    friendly_name: str = jfield(path="friendlyName")

    collections: list["PurviewCollection"] = jfield(
        init=False,
        default_factory=list,
    )

    parent: Optional["PurviewCollection"] = jfield(
        init=False,
        default=None,
    )

    parent_name: Optional[str] = jfield(
        path="parentCollection.referenceName",
        default=None,
    )

    @jproperty(path="parentCollection.type")
    def collection_reference(self) -> str:
        return "CollectionReference"

    def __post_asdict__(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.parent_name is None:
            del data["parentCollection"]

        return data

    def __repr__(self) -> str:
        if self.collections:
            return (
                f"{self.__class__.__name__}("
                f"name={self.name!r}, "
                f"friendly_name={self.friendly_name!r}, "
                f"collections={self.collections!r}, "
                f"parent_name={self.parent_name!r}"
                ")"
            )

        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, "
            f"friendly_name={self.friendly_name!r}, "
            f"parent_name={self.parent_name!r}"
            ")"
        )


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
