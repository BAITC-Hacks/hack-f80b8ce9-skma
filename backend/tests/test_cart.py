def propose(client, text, cart_id=None, session_id="s1"):
    response = client.post(
        "/api/chat", json={"session_id": session_id, "message": text, "cart_id": cart_id}
    )
    assert response.status_code == 200
    body = response.json()
    return body["cart_id"], body["pending"]


def cart(client, cart_id):
    return client.get(f"/api/cart/{cart_id}").json()


def confirm(client, cart_id, pending_id):
    return client.post(f"/api/cart/{cart_id}/confirm", json={"pending_id": pending_id})


def test_propose_does_not_change_cart(client):
    cart_id, pending = propose(client, "добавь 2 шт 200300290")
    assert pending["qty"] == 2
    assert cart(client, cart_id)["items"] == []


def test_confirm_adds_item(client):
    cart_id, pending = propose(client, "добавь 2 шт 200300290")
    response = confirm(client, cart_id, pending["pending_id"])
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["product_id"] == 2
    assert body["items"][0]["qty"] == 2
    assert body["total"] == 142000
    assert cart(client, cart_id) == body


def test_qty_clamped_to_stock_on_propose(client):
    _, pending = propose(client, "добавь 500 шт 200300290")
    assert pending["requested_qty"] == 500
    assert pending["qty"] == pending["max_qty"] == 19


def test_qty_clamped_again_on_confirm(client, ekt):
    cart_id, pending = propose(client, "добавь 15 шт 200300290")
    ekt.details[2]["quantity"] = 5  # someone bought the rest in between
    body = confirm(client, cart_id, pending["pending_id"]).json()
    assert body["items"][0]["qty"] == 5


def test_cart_total_never_exceeds_stock(client):
    cart_id, pending = propose(client, "добавь 15 шт 200300290")
    confirm(client, cart_id, pending["pending_id"])
    _, pending = propose(client, "добавь 15 шт 200300290", cart_id)
    body = confirm(client, cart_id, pending["pending_id"]).json()
    assert body["items"][0]["qty"] == 19


def test_confirm_when_stock_zero_returns_409(client, ekt):
    cart_id, pending = propose(client, "добавь 3 шт 200300290")
    ekt.details[2]["quantity"] = 0
    assert confirm(client, cart_id, pending["pending_id"]).status_code == 409
    assert cart(client, cart_id)["items"] == []


def test_out_of_stock_product_cannot_be_proposed(client):
    cart_id, pending = propose(client, "добавь 1 шт 200300285")
    assert pending is None
    assert cart(client, cart_id)["items"] == []


def test_confirm_unknown_pending_404(client):
    cart_id, _ = propose(client, "добавь 2 шт 200300290")
    assert confirm(client, cart_id, "nope").status_code == 404


def test_confirm_pending_from_other_cart_404(client):
    _, pending = propose(client, "добавь 2 шт 200300290", session_id="a")
    other_cart, _ = propose(client, "привет", session_id="b")
    assert confirm(client, other_cart, pending["pending_id"]).status_code == 404
    assert cart(client, other_cart)["items"] == []


def test_reject_then_confirm_404(client):
    cart_id, pending = propose(client, "добавь 2 шт 200300290")
    response = client.post(
        f"/api/cart/{cart_id}/reject", json={"pending_id": pending["pending_id"]}
    )
    assert response.status_code == 204
    assert confirm(client, cart_id, pending["pending_id"]).status_code == 404
    assert cart(client, cart_id)["items"] == []


def test_confirm_twice_adds_once(client):
    cart_id, pending = propose(client, "добавь 2 шт 200300290")
    assert confirm(client, cart_id, pending["pending_id"]).status_code == 200
    assert confirm(client, cart_id, pending["pending_id"]).status_code == 404
    assert cart(client, cart_id)["items"][0]["qty"] == 2


def test_new_proposal_replaces_old_one(client):
    cart_id, first = propose(client, "добавь 2 шт 200300290")
    propose(client, "добавь 1 шт 150200716", cart_id)
    assert confirm(client, cart_id, first["pending_id"]).status_code == 404


def test_unknown_cart_404(client):
    assert client.get("/api/cart/does-not-exist").status_code == 404


def test_client_cannot_choose_cart_id(client):
    cart_id, _ = propose(client, "привет", cart_id="my-own-id")
    assert cart_id != "my-own-id"
