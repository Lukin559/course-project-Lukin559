from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_item_success():
    """Test successful item creation."""
    item_data = {"name": "Test Item", "description": "A test item", "price": 10.99}
    response = client.post("/items", json=item_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"
    assert data["description"] == "A test item"
    assert data["price"] == 10.99
    assert "id" in data
    assert "created_at" in data


def test_create_item_minimal():
    """Test item creation with minimal data."""
    item_data = {"name": "Minimal Item"}
    response = client.post("/items", json=item_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Minimal Item"
    assert data["description"] is None
    assert data["price"] is None


def test_create_item_validation_error():
    """Test item creation with validation errors."""
    # Empty name
    response = client.post("/items", json={"name": ""})
    assert response.status_code == 422

    # Name too long
    response = client.post("/items", json={"name": "x" * 101})
    assert response.status_code == 422

    # Negative price
    response = client.post("/items", json={"name": "Test", "price": -1})
    assert response.status_code == 422


def test_get_item_success():
    """Test successful item retrieval."""
    # First create an item
    item_data = {"name": "Test Item"}
    create_response = client.post("/items", json=item_data)
    item_id = create_response.json()["id"]

    # Then get it
    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Item"
    assert data["id"] == item_id


def test_get_item_not_found():
    """Test item retrieval when item doesn't exist."""
    response = client.get("/items/999")
    assert response.status_code == 404
    data = response.json()
    assert "type" in data and "not_found" in data["type"]
    assert data["status"] == 404


def test_list_items():
    """Test listing all items."""
    # Create a few items
    client.post("/items", json={"name": "Item 1"})
    client.post("/items", json={"name": "Item 2"})

    response = client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert all("name" in item for item in data)


def test_update_item_success():
    """Test successful item update."""
    # Create an item
    item_data = {"name": "Original Name"}
    create_response = client.post("/items", json=item_data)
    item_id = create_response.json()["id"]

    # Update it
    update_data = {"name": "Updated Name", "price": 15.99}
    response = client.put(f"/items/{item_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["price"] == 15.99


def test_update_item_not_found():
    """Test item update when item doesn't exist."""
    update_data = {"name": "Updated Name"}
    response = client.put("/items/999", json=update_data)
    assert response.status_code == 404


def test_delete_item_success():
    """Test successful item deletion."""
    # Create an item
    item_data = {"name": "To Delete"}
    create_response = client.post("/items", json=item_data)
    item_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/items/{item_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/items/{item_id}")
    assert get_response.status_code == 404


def test_delete_item_not_found():
    """Test item deletion when item doesn't exist."""
    response = client.delete("/items/999")
    assert response.status_code == 404
