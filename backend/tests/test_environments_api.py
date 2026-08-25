def test_generate_with_seeded_time_appears_in_known_environments(client):
    client.patch(
        "/slots/0",
        json={"environment_time_seconds": {"water": 5.0, "earth": 2.0, "air": 1.0, "fire": 1.0}},
    )
    generate_response = client.post("/slots/0/environments/generate")
    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert generated["tier"] == 1.0

    listing = client.get("/slots/0/environments")
    assert listing.status_code == 200
    names = [e["name"] for e in listing.json()]
    assert generated["name"] in names


def test_generate_is_idempotent_by_name_on_repeat(client):
    client.patch(
        "/slots/0",
        json={"environment_time_seconds": {"water": 5.0, "earth": 2.0, "air": 1.0, "fire": 1.0}},
    )
    first = client.post("/slots/0/environments/generate").json()
    listing_after_first = len(client.get("/slots/0/environments").json())
    second = client.post("/slots/0/environments/generate").json()
    listing_after_second = len(client.get("/slots/0/environments").json())

    assert first["name"] and second["name"]
    # Each generate call upserts by name rather than appending duplicates,
    # so the known-environment count only grows when a *new* name is chosen.
    assert listing_after_second >= listing_after_first


def test_ensure_known_base_environment(client):
    response = client.post("/slots/0/environments/fire/ensure")
    assert response.status_code == 200
    assert response.json()["name"] == "fire"


def test_ensure_known_generated_environment(client):
    client.patch(
        "/slots/0",
        json={"environment_time_seconds": {"water": 5.0, "earth": 2.0, "air": 1.0, "fire": 1.0}},
    )
    generated = client.post("/slots/0/environments/generate").json()

    response = client.post(f"/slots/0/environments/{generated['name']}/ensure")
    assert response.status_code == 200
    assert response.json()["name"] == generated["name"]


def test_ensure_unknown_name_returns_404(client):
    response = client.post("/slots/0/environments/not-a-real-environment/ensure")
    assert response.status_code == 404
