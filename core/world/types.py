"""Type hierarchy and typed object definitions for the symbolic world model."""

from __future__ import annotations

from typing import Dict, List, Optional, Set


class TypeHierarchy:
    """Manages types and single-inheritance subtyping relationships."""

    def __init__(self) -> None:
        # parent -> direct children
        self._parents: Dict[str, Optional[str]] = {"object": None}

    def add_type(self, type_name: str, parent_type: str = "object") -> None:
        type_name = type_name.strip().lower()
        parent_type = parent_type.strip().lower()

        if parent_type not in self._parents:
            self._parents[parent_type] = "object"
        self._parents[type_name] = parent_type

    def is_subtype(self, child_type: str, parent_type: str) -> bool:
        """Returns True if child_type is identical to or descends from parent_type."""
        child = child_type.strip().lower()
        parent = parent_type.strip().lower()

        if parent == "object":
            return True
        curr: Optional[str] = child
        while curr is not None:
            if curr == parent:
                return True
            curr = self._parents.get(curr)
        return False

    def get_all_types(self) -> Set[str]:
        return set(self._parents.keys())


class TypedObject:
    """Represents a concrete named entity with an associated type."""

    def __init__(self, name: str, object_type: str = "object") -> None:
        self.name = name.strip()
        self.object_type = object_type.strip().lower()

    def __repr__(self) -> str:
        return f"{self.name}:{self.object_type}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypedObject):
            return False
        return self.name == other.name and self.object_type == other.object_type

    def __hash__(self) -> int:
        return hash((self.name, self.object_type))


class ObjectRegistry:
    """Registry of known objects and type hierarchy."""

    def __init__(self, hierarchy: Optional[TypeHierarchy] = None) -> None:
        self.hierarchy = hierarchy or TypeHierarchy()
        self._objects: Dict[str, TypedObject] = {}

    def register_type(self, type_name: str, parent_type: str = "object") -> None:
        self.hierarchy.add_type(type_name, parent_type)

    def register_object(self, name: str, object_type: str = "object") -> TypedObject:
        name = name.strip()
        obj_type = object_type.strip().lower()
        if obj_type not in self.hierarchy.get_all_types():
            self.hierarchy.add_type(obj_type, "object")
        obj = TypedObject(name, obj_type)
        self._objects[name] = obj
        return obj

    def get_object(self, name: str) -> Optional[TypedObject]:
        return self._objects.get(name.strip())

    def has_object(self, name: str) -> bool:
        return name.strip() in self._objects

    def get_type_of(self, name: str) -> Optional[str]:
        obj = self.get_object(name)
        return obj.object_type if obj else None

    def get_all_objects(self) -> Dict[str, str]:
        """Returns dict of name -> type."""
        return {name: obj.object_type for name, obj in self._objects.items()}

    def get_objects_of_type(self, target_type: str) -> List[str]:
        """Returns all object names matching or subtype of target_type."""
        return [
            name for name, obj in self._objects.items()
            if self.hierarchy.is_subtype(obj.object_type, target_type)
        ]
