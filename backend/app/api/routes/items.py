from fastapi import APIRouter, HTTPException, status

from app.schemas.item import Item, ItemCreate
from app.services.item_service import ItemServiceDep

router = APIRouter()


@router.get("", response_model=list[Item])
def list_items(service: ItemServiceDep) -> list[Item]:
    return service.list()


@router.post("", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(data: ItemCreate, service: ItemServiceDep) -> Item:
    return service.create(data)


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int, service: ItemServiceDep) -> Item:
    item = service.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, service: ItemServiceDep) -> None:
    if not service.delete(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
