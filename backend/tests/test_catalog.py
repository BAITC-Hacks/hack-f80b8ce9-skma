import json
from pathlib import Path

from app.services.catalog_service import to_card

FIXTURES = Path(__file__).parent / "fixtures"


def test_adapter_maps_fixture_fields():
    raw = json.loads((FIXTURES / "detail_515291.json").read_text(encoding="utf-8"))
    card = to_card(raw)
    assert card.id == 515291
    assert card.article == "200300285_"
    assert card.price == raw["price"]
    assert card.stock == raw["quantity"] == sum(s["quantity"] for s in raw["stores"])
    assert card.in_stock is True
    assert all(qty > 0 for qty in card.stores.values())
    assert card.specs["Количество полюсов"] == "3"
    assert not any(key.startswith("CML2_") for key in card.specs)
    assert card.certificate_url is None
    assert card.category == (
        "nizkovoltnaya_apparatura/silovye_avtomaticheskie_vyklyuchateli/drx250_mt_10_250_a_legrand"
    )


def test_get_product_returns_card(client, ekt):
    response = client.get("/api/catalog/2")
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 71000
    assert body["stock"] == 19
    assert body["stores"] == {"Алматы": 19}


def test_html_entities_in_names_are_decoded(client):
    assert client.get("/api/catalog/5").json()["name"].startswith('LED ЛАМПА A60 "Standart"')


def test_get_unknown_product_404(client):
    assert client.get("/api/catalog/999").status_code == 404


def test_detail_is_cached(client, ekt):
    client.get("/api/catalog/2")
    calls = ekt.calls
    client.get("/api/catalog/2")
    assert ekt.calls == calls


def test_catalog_down_returns_503(client, ekt):
    ekt.down = True
    assert client.get("/api/catalog/3").status_code == 503


def test_catalog_down_uses_cached_copy(client, catalog, ekt):
    client.get("/api/catalog/3")
    ekt.down = True
    catalog._details[3] = (-1e9, catalog._details[3][1])  # expire the cache entry
    assert client.get("/api/catalog/3").json()["stock"] == 13
