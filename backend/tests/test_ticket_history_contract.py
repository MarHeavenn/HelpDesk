"""HU-09 T4 - contrato HTTP del historial (RF-81, RF-83, RF-89)."""

from app.main import app


def test_history_is_the_only_new_path_and_uses_get():
    paths = app.openapi()["paths"]

    assert set(paths["/api/tickets/{ticket_id}/history"]) == {"get"}
    history_paths = [path for path in paths if "history" in path.lower()]
    assert history_paths == ["/api/tickets/{ticket_id}/history"]


def test_history_response_declares_the_documented_fields():
    schema = app.openapi()
    event = schema["components"]["schemas"]["HistoryEventResponse"]
    user = schema["components"]["schemas"]["HistoryUserResponse"]

    assert list(event["properties"]) == [
        "action",
        "actor",
        "occurred_at",
        "previous_value",
        "new_value",
        "previous_assignee",
        "new_assignee",
        "comment",
    ]
    assert set(event["required"]) == {
        "action",
        "actor",
        "occurred_at",
        "previous_value",
        "new_value",
        "previous_assignee",
        "new_assignee",
        "comment",
    }
    assert list(user["properties"]) == ["id", "name"]


def test_ticket_contract_does_not_gain_history_fields():
    schema = app.openapi()
    ticket = schema["components"]["schemas"]["TicketResponse"]

    assert set(ticket["properties"]) == {
        "id",
        "title",
        "description",
        "priority",
        "status",
        "assignee",
        "requester",
        "sla",
        "created_at",
        "resolved_at",
        "requester_id",
    }
    assert not {"action", "occurred_at", "previous_value", "comment"} & set(
        ticket["properties"]
    )


def test_history_route_has_no_query_parameters():
    operation = app.openapi()["paths"]["/api/tickets/{ticket_id}/history"]["get"]

    query_parameters = [
        parameter
        for parameter in operation.get("parameters", [])
        if parameter["in"] == "query"
    ]
    assert query_parameters == []
