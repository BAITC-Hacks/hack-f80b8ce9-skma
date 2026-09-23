def test_create_and_list_items(client):
    response = client.post("/api/items", json={"title": "First"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "title": "First", "description": None}

    response = client.get("/api/items")
    assert response.json() == [{"id": 1, "title": "First", "description": None}]


def test_get_missing_item_returns_404(client):
    assert client.get("/api/items/999").status_code == 404


def test_delete_item(client):
    item_id = client.post("/api/items", json={"title": "Temp"}).json()["id"]
    assert client.delete(f"/api/items/{item_id}").status_code == 204
    assert client.get(f"/api/items/{item_id}").status_code == 404


def test_create_item_validates_title(client):
    assert client.post("/api/items", json={"title": ""}).status_code == 422
