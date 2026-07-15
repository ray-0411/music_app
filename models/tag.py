from dataclasses import dataclass


@dataclass(frozen=True)
class TagCategory:
    id: int
    name: str
    sort_order: int
    is_available: bool


@dataclass(frozen=True)
class TagOption:
    id: int
    category_id: int
    name: str
    sort_order: int
    is_available: bool

