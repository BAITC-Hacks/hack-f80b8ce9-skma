from typing import Annotated

from fastapi import Depends

from app.schemas.item import Item, ItemCreate


class ItemService:
    """In-memory storage. Replace with a real database when needed."""

    def __init__(self) -> None:
        self._items: dict[int, Item] = {}
        self._next_id = 1

    def list(self) -> list[Item]:
        return list(self._items.values())

    def get(self, item_id: int) -> Item | None:
        return self._items.get(item_id)

    def create(self, data: ItemCreate) -> Item:
        item = Item(id=self._next_id, **data.model_dump())
        self._items[item.id] = item
        self._next_id += 1
        return item

    def delete(self, item_id: int) -> bool:
        return self._items.pop(item_id, None) is not None


item_service = ItemService()


def get_item_service() -> ItemService:
    return item_service


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
