def test_list_slots_returns_three_seeded_slots(client):
    response = client.get("/slots")
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) == 3
    assert {s["id"] for s in slots} == {0, 1, 2}
    assert all(s["used"] is False for s in slots)


def test_get_slot_detail_shape(client):
    response = client.get("/slots/0")
    assert response.status_code == 200
    detail = response.json()
    assert detail["environment_slot_keys"] == ["water", "earth", "air", "fire"]
    assert detail["environment_time_seconds"] == {
        "water": 0.0,
        "earth": 0.0,
        "air": 0.0,
        "fire": 0.0,
    }
    assert detail["known_environments"] == {}


def test_get_missing_slot_returns_404(client):
    response = client.get("/slots/99")
    assert response.status_code == 404


def test_patch_slot_persists_and_is_reflected_on_get(client):
    response = client.patch(
        "/slots/0",
        json={
            "current_tab": "environment",
            "time_alive_seconds": 12.5,
            "selected_environment": "fire",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_tab"] == "environment"
    assert body["time_alive_seconds"] == 12.5
    assert body["selected_environment"] == "fire"
    assert body["used"] is True

    refetched = client.get("/slots/0").json()
    assert refetched["current_tab"] == "environment"
    assert refetched["time_alive_seconds"] == 12.5


def test_patch_slot_invalid_evolution_stage_returns_422(client):
    response = client.patch("/slots/0", json={"evolution_stage": "not-a-stage"})
    assert response.status_code == 422


def test_patch_slot_invalid_click_progress_returns_422(client):
    response = client.patch("/slots/0", json={"evolution_click_progress": 5})
    assert response.status_code == 422


def test_new_slot_resets_to_defaults(client):
    client.patch("/slots/0", json={"time_alive_seconds": 500.0, "evolution_stage": "petawaru"})
    response = client.post("/slots/0/new")
    assert response.status_code == 200
    body = response.json()
    assert body["time_alive_seconds"] == 0.0
    assert body["evolution_stage"] == "dormant"
    assert body["used"] is True
    assert body["known_environments"] == {}


def test_reset_slot_keeps_known_environments(client):
    generate_response = client.post("/slots/0/environments/generate")
    assert generate_response.status_code == 200
    discovered_name = generate_response.json()["name"]
    client.patch("/slots/0", json={"time_alive_seconds": 500.0})

    response = client.post("/slots/0/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["time_alive_seconds"] == 0.0
    assert body["evolution_stage"] == "dormant"
    assert discovered_name in body["known_environments"]


def test_patch_environment_slot_keys_must_have_four_entries(client):
    response = client.patch("/slots/0", json={"environment_slot_keys": ["fire", "water"]})
    assert response.status_code == 422


def test_crossing_unlock_threshold_reveals_hidden_environment(client):
    # Threshold is FIRST_CYCLE_THRESHOLD_SECONDS_TEST (10.0) in app.progression.
    response = client.patch(
        "/slots/0",
        json={"environment_time_seconds": {"water": 3.0, "earth": 3.0, "air": 2.0, "fire": 3.0}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hidden_revealed"] is True
    assert body["hidden_environment_name"]
    assert body["awaiting_hidden_relock_choice"] is True
    assert body["current_tab"] == "environment"


def test_below_threshold_does_not_reveal(client):
    response = client.patch(
        "/slots/0",
        json={"environment_time_seconds": {"water": 1.0, "earth": 1.0, "air": 1.0, "fire": 1.0}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hidden_revealed"] is False
    assert body["hidden_environment_name"] is None


def test_resolving_relock_choice_replaces_slot_and_advances_cycle(client):
    revealed = client.patch(
        "/slots/0",
        json={"environment_time_seconds": {"water": 3.0, "earth": 3.0, "air": 2.0, "fire": 3.0}},
    ).json()
    hidden_name = revealed["hidden_environment_name"]

    new_keys = ["fire", "earth", "air", hidden_name]
    resolved = client.patch(
        "/slots/0",
        json={
            "environment_slot_keys": new_keys,
            "hidden_revealed": False,
            "hidden_environment_name": None,
            "selected_environment": None,
            "environment_time_seconds": {k: 0.0 for k in new_keys},
            "hidden_cycle_index": revealed["hidden_cycle_index"] + 1,
            "awaiting_hidden_relock_choice": False,
        },
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["environment_slot_keys"] == new_keys
    assert body["hidden_revealed"] is False
    assert body["awaiting_hidden_relock_choice"] is False
    assert body["hidden_cycle_index"] == revealed["hidden_cycle_index"] + 1
    assert body["environment_time_seconds"] == {k: 0.0 for k in new_keys}
