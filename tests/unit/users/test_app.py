"""
Unit tests for src/users/lambda_function.py

Coverage:
  - All CRUD operations via handler() with an in-memory DynamoDB table (moto)
  - Handler routing for every supported HTTP method
  - Error cases: missing required fields, nonexistent users, invalid methods
  - Both API Gateway v1 (httpMethod) and v2 (requestContext.http.method) event shapes
  - Helper functions: get_method, get_user_id, parse_body, build_response

All tests are self-contained: no real AWS calls are made.
"""
import json
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

import lambda_function
from tests.unit.users.conftest import (
    make_event,
    make_v2_event,
    seed_user,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def invoke(event):
    """Call handler() and attach a `parsed` key with the decoded body."""
    resp = lambda_function.handler(event, None)
    resp["parsed"] = json.loads(resp["body"])
    return resp


def ddb_error(operation="Scan"):
    return ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "simulated failure"}},
        operation,
    )


# ── helper function unit tests ────────────────────────────────────────────────

class TestGetMethod:
    """get_method() extracts the HTTP verb from v1 and v2 event shapes."""

    def test_v1_event_returns_method(self):
        assert lambda_function.get_method({"httpMethod": "GET", "requestContext": {}}) == "GET"

    def test_v2_event_returns_method(self):
        event = {"requestContext": {"http": {"method": "POST"}}}
        assert lambda_function.get_method(event) == "POST"

    def test_v2_takes_priority_when_both_present(self):
        # requestContext.http is checked first; httpMethod is the REST API v1 fallback
        event = {"httpMethod": "DELETE", "requestContext": {"http": {"method": "GET"}}}
        assert lambda_function.get_method(event) == "GET"

    def test_neither_present_returns_empty_string(self):
        assert lambda_function.get_method({"requestContext": {}}) == ""


class TestGetUserId:
    """get_user_id() extracts the userid path parameter."""

    def test_returns_userid_when_present(self):
        event = {"pathParameters": {"userid": "abc-123"}}
        assert lambda_function.get_user_id(event) == "abc-123"

    def test_returns_none_when_path_parameters_is_none(self):
        assert lambda_function.get_user_id({"pathParameters": None}) is None

    def test_returns_none_when_userid_key_missing(self):
        assert lambda_function.get_user_id({"pathParameters": {}}) is None


class TestParseBody:
    """parse_body() deserialises the event body string."""

    def test_parses_valid_json_string(self):
        assert lambda_function.parse_body({"body": '{"key": "val"}'}) == {"key": "val"}

    def test_raises_value_error_on_invalid_json(self):
        with pytest.raises(ValueError):
            lambda_function.parse_body({"body": "not-json"})

    def test_none_body_returns_empty_dict(self):
        # `body or "{}"` coerces None → "{}" → returns {}
        assert lambda_function.parse_body({"body": None}) == {}


class TestBuildResponse:
    """build_response() shapes the API Gateway proxy response."""

    def test_correct_status_code(self):
        assert lambda_function.build_response(200, {})["statusCode"] == 200

    def test_body_is_json_string(self):
        resp = lambda_function.build_response(200, {"ok": True})
        assert json.loads(resp["body"]) == {"ok": True}

    def test_cors_header_present(self):
        resp = lambda_function.build_response(200, {})
        assert "Access-Control-Allow-Origin" in resp["headers"]

    def test_all_common_status_codes(self):
        for code in (200, 201, 400, 404, 405, 500):
            assert lambda_function.build_response(code, {})["statusCode"] == code


# ── GET /users (list_users) ───────────────────────────────────────────────────

class TestListUsers:
    def test_empty_table_returns_empty_list(self, ddb_table):
        resp = invoke(make_event("GET"))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["users"] == []

    def test_returns_all_seeded_items(self, ddb_table):
        seed_user(ddb_table, userid="u1", email="a@example.com")
        seed_user(ddb_table, userid="u2", email="b@example.com")
        resp = invoke(make_event("GET"))
        assert resp["statusCode"] == 200
        assert len(resp["parsed"]["users"]) == 2

    def test_dynamodb_error_returns_500(self, ddb_table):
        with patch.object(lambda_function.table, "scan", side_effect=ddb_error("Scan")):
            resp = invoke(make_event("GET"))
        assert resp["statusCode"] == 500


# ── GET /users/{userid} (get_user) ───────────────────────────────────────────

class TestGetUser:
    def test_returns_existing_user(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("GET", userid=user["userid"]))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["userid"] == user["userid"]
        assert resp["parsed"]["email"] == user["email"]

    def test_unknown_userid_returns_404(self, ddb_table):
        resp = invoke(make_event("GET", userid="does-not-exist"))
        assert resp["statusCode"] == 404

    def test_no_userid_param_falls_through_to_list(self, ddb_table):
        # pathParameters=None → get_user_id returns None → handler calls list_users
        resp = invoke(make_event("GET", userid=None))
        assert resp["statusCode"] == 200
        assert "users" in resp["parsed"]

    def test_dynamodb_error_returns_500(self, ddb_table):
        with patch.object(lambda_function.table, "get_item", side_effect=ddb_error("GetItem")):
            resp = invoke(make_event("GET", userid="u1"))
        assert resp["statusCode"] == 500


# ── POST /users (create_user) ─────────────────────────────────────────────────

class TestCreateUser:
    VALID = {"first_name": "Alice", "last_name": "Smith", "email": "Alice@Example.COM"}

    def test_valid_body_returns_201(self, ddb_table):
        resp = invoke(make_event("POST", body=self.VALID))
        assert resp["statusCode"] == 201

    def test_auto_generates_userid(self, ddb_table):
        resp = invoke(make_event("POST", body=self.VALID))
        assert resp["parsed"].get("userid")

    def test_email_is_stored_lowercase(self, ddb_table):
        resp = invoke(make_event("POST", body=self.VALID))
        assert resp["parsed"]["email"] == "alice@example.com"

    def test_item_written_to_dynamodb(self, ddb_table):
        resp = invoke(make_event("POST", body=self.VALID))
        userid = resp["parsed"]["userid"]
        item = ddb_table.get_item(Key={"userid": userid}).get("Item")
        assert item is not None
        assert item["first_name"] == "Alice"

    def test_missing_first_name_returns_400(self, ddb_table):
        body = {"last_name": "Smith", "email": "a@example.com"}
        assert invoke(make_event("POST", body=body))["statusCode"] == 400

    def test_missing_last_name_returns_400(self, ddb_table):
        body = {"first_name": "Alice", "email": "a@example.com"}
        assert invoke(make_event("POST", body=body))["statusCode"] == 400

    def test_missing_email_returns_400(self, ddb_table):
        body = {"first_name": "Alice", "last_name": "Smith"}
        assert invoke(make_event("POST", body=body))["statusCode"] == 400

    def test_invalid_json_body_returns_400(self, ddb_table):
        event = make_event("POST")
        event["body"] = "not-json"
        assert invoke(event)["statusCode"] == 400

    def test_none_body_returns_400(self, ddb_table):
        assert invoke(make_event("POST", body=None))["statusCode"] == 400

    def test_dynamodb_error_returns_500(self, ddb_table):
        with patch.object(lambda_function.table, "put_item", side_effect=ddb_error("PutItem")):
            assert invoke(make_event("POST", body=self.VALID))["statusCode"] == 500


# ── PUT /users/{userid} (update_user) ────────────────────────────────────────

class TestUpdateUser:
    def test_update_single_field(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("PUT", userid=user["userid"], body={"email": "new@example.com"}))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["email"] == "new@example.com"

    def test_update_all_allowed_fields(self, ddb_table):
        user = seed_user(ddb_table)
        updates = {"first_name": "Updated", "last_name": "Name", "email": "up@example.com"}
        resp = invoke(make_event("PUT", userid=user["userid"], body=updates))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["first_name"] == "Updated"
        assert resp["parsed"]["last_name"] == "Name"

    def test_nonexistent_user_returns_404(self, ddb_table):
        resp = invoke(make_event("PUT", userid="ghost", body={"email": "x@x.com"}))
        assert resp["statusCode"] == 404

    def test_no_valid_fields_in_body_returns_400(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("PUT", userid=user["userid"], body={"unknown": "field"}))
        assert resp["statusCode"] == 400

    def test_invalid_json_returns_400(self, ddb_table):
        event = make_event("PUT", userid="u1")
        event["body"] = "bad-json"
        assert invoke(event)["statusCode"] == 400

    def test_dynamodb_update_error_returns_500(self, ddb_table):
        user = seed_user(ddb_table)
        with patch.object(lambda_function.table, "update_item", side_effect=ddb_error("UpdateItem")):
            resp = invoke(make_event("PUT", userid=user["userid"], body={"email": "x@x.com"}))
        assert resp["statusCode"] == 500

    def test_dynamodb_get_before_update_error_returns_500(self, ddb_table):
        # Covers lines 106-108: get_item raises ClientError during the existence
        # check inside update_user (before the actual update_item call).
        user = seed_user(ddb_table)
        with patch.object(lambda_function.table, "get_item", side_effect=ddb_error("GetItem")):
            resp = invoke(make_event("PUT", userid=user["userid"], body={"email": "x@x.com"}))
        assert resp["statusCode"] == 500


# ── DELETE /users/{userid} (delete_user) ─────────────────────────────────────

class TestDeleteUser:
    def test_existing_user_deleted_returns_200(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("DELETE", userid=user["userid"]))
        assert resp["statusCode"] == 200

    def test_item_removed_from_dynamodb(self, ddb_table):
        user = seed_user(ddb_table)
        invoke(make_event("DELETE", userid=user["userid"]))
        result = ddb_table.get_item(Key={"userid": user["userid"]})
        assert "Item" not in result

    def test_nonexistent_user_returns_404(self, ddb_table):
        resp = invoke(make_event("DELETE", userid="ghost"))
        assert resp["statusCode"] == 404

    def test_dynamodb_delete_error_returns_500(self, ddb_table):
        user = seed_user(ddb_table)
        with patch.object(lambda_function.table, "delete_item", side_effect=ddb_error("DeleteItem")):
            resp = invoke(make_event("DELETE", userid=user["userid"]))
        assert resp["statusCode"] == 500

    def test_dynamodb_get_before_delete_error_returns_500(self, ddb_table):
        # Covers lines 135-137: get_item raises ClientError during the existence
        # check inside delete_user (before the actual delete_item call).
        user = seed_user(ddb_table)
        with patch.object(lambda_function.table, "get_item", side_effect=ddb_error("GetItem")):
            resp = invoke(make_event("DELETE", userid=user["userid"]))
        assert resp["statusCode"] == 500


# ── Handler routing ───────────────────────────────────────────────────────────

class TestHandlerRouting:
    """Verify the dispatcher sends each HTTP method to the right operation."""

    def test_get_without_userid_calls_list_users(self, ddb_table):
        resp = invoke(make_event("GET"))
        assert resp["statusCode"] == 200
        assert "users" in resp["parsed"]

    def test_get_with_userid_calls_get_user(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("GET", userid=user["userid"]))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["userid"] == user["userid"]

    def test_post_calls_create_user(self, ddb_table):
        body = {"first_name": "Bob", "last_name": "Jones", "email": "b@example.com"}
        resp = invoke(make_event("POST", body=body))
        assert resp["statusCode"] == 201

    def test_put_calls_update_user(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("PUT", userid=user["userid"], body={"email": "upd@example.com"}))
        assert resp["statusCode"] == 200

    def test_delete_calls_delete_user(self, ddb_table):
        user = seed_user(ddb_table)
        resp = invoke(make_event("DELETE", userid=user["userid"]))
        assert resp["statusCode"] == 200

    def test_options_returns_200(self, ddb_table):
        resp = invoke(make_event("OPTIONS"))
        assert resp["statusCode"] == 200

    def test_unsupported_method_returns_405(self, ddb_table):
        resp = invoke(make_event("PATCH"))
        assert resp["statusCode"] == 405

    def test_head_returns_405(self, ddb_table):
        resp = invoke(make_event("HEAD"))
        assert resp["statusCode"] == 405

    def test_v2_event_shape_routes_correctly(self, ddb_table):
        # HTTP API v2 events use requestContext.http.method instead of httpMethod
        body = {"first_name": "V2", "last_name": "User", "email": "v2@example.com"}
        resp = invoke(make_v2_event("POST", body=body))
        assert resp["statusCode"] == 201

    def test_v2_list_users(self, ddb_table):
        seed_user(ddb_table)
        resp = invoke(make_v2_event("GET"))
        assert resp["statusCode"] == 200
        assert len(resp["parsed"]["users"]) == 1

    def test_unexpected_exception_returns_500(self, ddb_table):
        # Covers lines 175-177: the bare `except Exception` in handler catches
        # anything that isn't a ValueError (e.g. a RuntimeError from deep inside).
        with patch.object(lambda_function.table, "scan", side_effect=RuntimeError("boom")):
            resp = invoke(make_event("GET"))
        assert resp["statusCode"] == 500
        assert resp["parsed"]["error"] == "Internal server error"
