import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from jdataclass import asdict, create, jfield, jproperty

__USER_MATCHER_NAME__ = "principal.microsoft.id"
__GROUP_MATCHER_NAME__ = "principal.microsoft.groups"
__ROLE_RULES_IDS__ = [
    "purviewmetadatarole_builtin_collection-administrator",
    "purviewmetadatarole_builtin_data-source-administrator",
    "purviewmetadatarole_builtin_data-curator",
    "purviewmetadatarole_builtin_purview-reader",
    "purviewmetadatarole_builtin_insights-reader",
    "purviewmetadatarole_builtin_policy-author",
    "purviewmetadatarole_builtin_workflow-administrator",
]


@dataclass
class MetadataPolicy:
    id: str
    name: str
    properties: "MetadataPolicyProperties"
    version: int


@dataclass
class MetadataPolicyProperties:
    description: str = field(default="")

    decision_rules: dict[str, Any] = jfield(
        path="decisionRules",
        default_factory=dict,
    )

    attribute_rules: list["AttributeRule"] = field(
        init=False,
        default_factory=list,
    )

    collection: dict[str, Any] = field(default_factory=dict)
    parent_collection_name: Optional[str] = jfield(
        path="parentCollectionName",
        default=None,
    )

    @property
    def collection_name(self):
        return self.collection.get("referenceName", "")

    @jproperty(path="attributeRules")
    def _attribute_rules(self) -> list["AttributeRule"]:
        return [rule for rule in self.attribute_rules if rule.conditions]

    @_attribute_rules.setter
    def _attribute_rules(self, value: list["AttributeRule"]):
        self.attribute_rules = value

    def get_rule_by_id(self, rule_id: str):
        id_prefix = rule_id.split(":")[0]
        for rule in self.attribute_rules:
            if rule.id.startswith(id_prefix):
                return rule

        rule_id = f"{id_prefix}:{self.collection_name}"
        rule = AttributeRule(
            id=rule_id,
            name=rule_id,
            kind="attributerule",
            parent=self,
        )
        self.attribute_rules.append(rule)
        return rule

    def __post_asdict__(self, value: dict[str, Any]):
        return {k: v for k, v in value.items() if v is not None}


@dataclass
class AttributeRule:
    id: str
    kind: str
    name: str
    conditions: list[list["AttributeMatcher"]] = field(
        init=False,
        default_factory=list,
    )
    parent: "MetadataPolicyProperties" = jfield(parent_ref=True)

    def __post_init__(self):
        if not self.conditions:
            self.conditions.append(self._create_users_conditions())
            self.conditions.append(self._create_groups_conditions())

    def _create_users_conditions(
        self,
        users: Optional[list[str]] = None,
    ) -> Any:
        rule_id = self.id.split(":")[0]
        return [
            UserMatcher(users),
            DerivedRoleMatcher(rule_id),
        ]

    def _create_groups_conditions(
        self,
        groups: Optional[list[str]] = None,
    ) -> Any:
        rule_id = self.id.split(":")[0]
        return [
            GroupMatcher(groups),
            DerivedRoleMatcher(rule_id),
        ]

    def add_user(self, object_id: str):
        if matcher := self.users_matcher:
            matcher.add_value_inclued_in(object_id)

    @property
    def users_matcher(self):
        for condition in self.conditions:
            for matcher in condition:
                if matcher.is_user_permission:
                    return matcher

    def add_group(self, object_id: str):
        if matcher := self.groups_matcher:
            matcher.add_value_inclued_in(object_id)

    @property
    def groups_matcher(self):
        for condition in self.conditions:
            for matcher in condition:
                if matcher.is_group_permission:
                    return matcher

    @property
    def has_values(self):
        return self.has_users or self.has_groups

    @property
    def has_users(self):
        return (matcher := self.users_matcher) and matcher.values

    @property
    def has_groups(self):
        return (matcher := self.groups_matcher) and matcher.values

    @jproperty(path="dnfCondition")
    def _conditions(self) -> list[list["AttributeMatcher"]]:
        if self.is_role_rule:
            conditions: list[list["AttributeMatcher"]] = []

            if self.has_users and (matcher := self.users_matcher):
                conditions.append(
                    self._create_users_conditions(matcher.values),
                )

            if self.has_groups and (matcher := self.groups_matcher):
                conditions.append(
                    self._create_groups_conditions(matcher.values),
                )

            return conditions

        if self.is_permission_rule:
            return [
                [DerivedPermissionMatcher(rule.id)]
                for rule in self._get_rules_with_values()
            ]

        return []

    def _get_rules_with_values(self):
        for rule_id in __ROLE_RULES_IDS__:
            if (
                rule := self.parent.get_rule_by_id(rule_id)
            ) and rule.has_values:
                yield rule

    @_conditions.setter
    def _conditions(self, value: list[list["AttributeMatcher"]]):
        self.conditions = value

    @property
    def is_role_rule(self):
        return self.id.startswith("purviewmetadatarole")

    @property
    def is_permission_rule(self):
        return self.id.startswith("permission")


@dataclass
class AttributeMatcher:
    attribute_name: str = jfield(path="attributeName")
    from_rule: Optional[str] = jfield(path="fromRule", default=None)

    value_includes: Optional[str] = jfield(
        path="attributeValueIncludes",
        default=None,
    )
    value_included_in: Optional[list[str]] = jfield(
        path="attributeValueIncludedIn",
        default=None,
    )

    value_excludes: Optional[str] = jfield(
        path="attributeValueExcludes",
        default=None,
    )
    value_excluded_in: Optional[list[str]] = jfield(
        path="attributeValueExcludedIn",
        default=None,
    )

    @property
    def is_user_permission(self):
        return self.attribute_name == __USER_MATCHER_NAME__

    @property
    def is_group_permission(self):
        return self.attribute_name == __GROUP_MATCHER_NAME__

    @property
    def values(self):
        if self.value_included_in is None:
            self.value_included_in = []

        return self.value_included_in

    def add_value_inclued_in(self, value: str):
        values = self.values
        distinct = set(values + [value])
        values.clear()
        values.extend(distinct)

    def __post_asdict__(self, value: dict[str, Any]):
        return {k: v for k, v in value.items() if v is not None}


class UserMatcher(AttributeMatcher):
    def __init__(self, users: Optional[list[str]] = None):
        if users is None:
            users = []

        super().__init__(__USER_MATCHER_NAME__, value_included_in=users)


class GroupMatcher(AttributeMatcher):
    def __init__(self, groups: Optional[list[str]] = None):
        if groups is None:
            groups = []

        super().__init__(__GROUP_MATCHER_NAME__, value_included_in=groups)


class DerivedRoleMatcher(AttributeMatcher):
    def __init__(self, rule_id: str):
        super().__init__(
            "derived.purview.role",
            from_rule=rule_id,
            value_includes=rule_id,
        )


class DerivedPermissionMatcher(AttributeMatcher):
    def __init__(self, rule_id: str):
        super().__init__(
            "derived.purview.permission",
            from_rule=rule_id,
            value_includes=rule_id,
        )


def test_add_user_to_rule():
    """
    >>> test_add_user_to_rule()

    """
    dirname = os.path.dirname(__file__)
    initial_json_path = os.path.join(
        dirname,
        "metadata_policy.json",
    )
    expected_json_path = os.path.join(
        dirname,
        "metadata_policy_with_insigths_reader.json",
    )

    initial_json_data = json.load(open(initial_json_path))
    expected_json_data = json.load(open(expected_json_path))

    policy = create(MetadataPolicy, initial_json_data)
    if rule := policy.properties.get_rule_by_id(
        "purviewmetadatarole_builtin_insights-reader"
    ):
        rule.add_user("00000000-0000-0000-0000-000000000000")

    assert asdict(policy) == expected_json_data


if __name__ == "__main__":
    import doctest

    doctest.testmod()
