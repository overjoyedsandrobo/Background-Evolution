import api_client
import responses
from config import BACKEND_BASE_URL
from requests.exceptions import ConnectionError as RequestsConnectionError


@responses.activate
def test_list_slots_parses_json_list():
    responses.add(
        responses.GET,
        f"{BACKEND_BASE_URL}/slots",
        json=[{"id": 0, "used": False}],
        status=200,
    )
    result = api_client.list_slots()
    assert result == [{"id": 0, "used": False}]


@responses.activate
def test_get_slot_hits_correct_path():
    responses.add(
        responses.GET,
        f"{BACKEND_BASE_URL}/slots/2",
        json={"id": 2, "used": True},
        status=200,
    )
    result = api_client.get_slot(2)
    assert result["id"] == 2
    assert responses.calls[0].request.url.endswith("/slots/2")


@responses.activate
def test_new_slot_posts_to_correct_path():
    responses.add(
        responses.POST,
        f"{BACKEND_BASE_URL}/slots/1/new",
        json={"id": 1, "used": True},
        status=200,
    )
    result = api_client.new_slot(1)
    assert result["used"] is True


@responses.activate
def test_patch_slot_sends_json_body():
    responses.add(
        responses.PATCH,
        f"{BACKEND_BASE_URL}/slots/0",
        json={"id": 0, "current_tab": "environment"},
        status=200,
    )
    result = api_client.patch_slot(0, current_tab="environment", time_alive_seconds=12.5)
    assert result["current_tab"] == "environment"
    sent_body = responses.calls[0].request.body
    assert (
        b'"current_tab": "environment"' in sent_body or b'"current_tab":"environment"' in sent_body
    )


@responses.activate
def test_connection_error_raises_backend_unavailable():
    responses.add(
        responses.GET,
        f"{BACKEND_BASE_URL}/slots",
        body=RequestsConnectionError("refused"),
    )
    try:
        api_client.list_slots()
        raise AssertionError("expected BackendUnavailableError")
    except api_client.BackendUnavailableError:
        pass


@responses.activate
def test_http_error_status_raises_backend_unavailable():
    responses.add(
        responses.GET,
        f"{BACKEND_BASE_URL}/slots/99",
        json={"detail": "not found"},
        status=404,
    )
    try:
        api_client.get_slot(99)
        raise AssertionError("expected BackendUnavailableError")
    except api_client.BackendUnavailableError:
        pass


@responses.activate
def test_health_check_parses_status():
    responses.add(
        responses.GET,
        f"{BACKEND_BASE_URL}/health",
        json={"status": "ok"},
        status=200,
    )
    assert api_client.health_check() == {"status": "ok"}
