def search(client, q):
    response = client.get("/api/catalog/search", params={"q": q})
    assert response.status_code == 200
    return response.json()


def test_search_by_exact_article_is_first(client):
    assert search(client, "Есть в наличии 200300285_?")[0]["id"] == 1
    assert search(client, "200300285")[0]["id"] == 1


def test_search_by_manufacturer_code(client):
    assert search(client, "027105")[0]["id"] == 3


def test_search_by_name_fuzzy(client):
    assert search(client, "лампа standrt E27")[0]["id"] == 5


def test_analogs_for_zero_stock(client):
    analogs = client.get("/api/catalog/1/analogs").json()
    assert len(analogs) >= 1
    assert all(a["stock"] > 0 for a in analogs)
    assert all(a["category"] == analogs[0]["category"] for a in analogs)
    assert {a["id"] for a in analogs} <= {2, 3}


def test_best_analog_has_same_rating(client):
    # 027230 has the same current (160А) as 027228, 027105 only the same breaking capacity.
    assert client.get("/api/catalog/1/analogs").json()[0]["id"] == 2


def test_analog_reason_mentions_matched_values(client):
    reason = client.get("/api/catalog/1/analogs").json()[0]["reason"]
    assert "160А" in reason
    assert "в наличии 19 шт." in reason


def test_analogs_exclude_original(client):
    assert 1 not in {a["id"] for a in client.get("/api/catalog/1/analogs").json()}


def test_search_understands_customer_words(client):
    # Customers say "автомат", the catalog writes "АВ".
    assert search(client, "автомат DRX250 125А")[0]["id"] == 4
