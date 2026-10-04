"""
Unit tests for src/users/lambda_function.py

All DynamoDB calls are intercepted by moto — no real AWS traffic.
The ddb_table fixture reloads lambda_function so its module-level `table`
object re-binds to the mocked resource for each test.
"""
import json
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

import lambda_function
from tests.conftest import make_event, make_v2_event, seed_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call(event):
    """Invoke the Lambda handler and parse the JSON body."""
    resp = lambda_function.handler(event, None)
    resp["parsed"] = json.loads(resp["body"])
    return resp


def client_error(operation="Scan"):
    return ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "simulated failure"}},
        operation,
    )


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

class TestGetMethod:
    def test_v1_event(self):
        assert lambda_function.get_method({"httpMethod": "GET", "requestContext": {}}) == "GET"

    def test_v2_event(self):
        event = {"requestContext": {"http": {"method": "POST"}}}
        assert lambda_function.get_method(event) == "POST"

    def test_v2_takes_priority_over_v1(self):
        # v2 (requestContext.http.method) is checked first; v1 httpMethod is the fallback
        event = {"httpMethod": "DELETE", "requestContext": {"http": {"method": "GET"}}}
        assert lambda_function.get_method(event) == "GET"

    def test_neither_returns_empty_string(self):
        # no httpMethod and no requestContext.http → returns "" (falsy, not None)
        assert lambda_function.get_method({"requestContext": {}}) == ""


class TestGetUserId:
    def test_present(self):
        assert lambda_function.get_user_id({"pathParameters": {"userid": "abc"}}) == "abc"

    def test_none_path_parameters(self):
        assert lambda_function.get_user_id({"pathParameters": None}) is None

    def test_missing_key(self):
        assert lambda_function.get_user_id({"pathParameters": {}}) is None


class TestParseBody:
    def test_valid_json(self):
        event = {"body": '{"key": "value"}'}
        assert lambda_function.parse_body(event) == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            lambda_function.parse_body({"body": "not-json"})

    def test_none_body_returns_empty_dict(self):
        # `body or "{}"` coerces None to "{}", so parse_body returns {} without raising
        assert lambda_function.parse_body({"body": None}) == {}


class TestBuildResponse:
    def test_shape(self):
        resp = lambda_function.build_response(200, {"ok": True})
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"]) == {"ok": True}
        assert "Access-Control-Allow-Origin" in resp["headers"]

    def test_status_codes_preserved(self):
        for code in (200, 201, 400, 404, 500):
            assert lambda_function.build_response(code, {})["statusCode"] == code


# ---------------------------------------------------------------------------
# list_users  GET /users
# ---------------------------------------------------------------------------

class TestListUsers:
    def test_empty_table(self, ddb_table):
        resp = call(make_event("GET"))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["users"] == []

    def test_returns_all_items(self, ddb_table):
        seed_user(ddb_table, userid="u1", email="a@example.com")
        seed_user(ddb_table, userid="u2", email="b@example.com")
        resp = call(make_event("GET"))
        assert resp["statusCode"] == 200
        assert len(resp["parsed"]["users"]) == 2

    def test_dynamodb_error_returns_500(self, ddb_table):
        with patch.object(lambda_function.table, "scan", side_effect=client_error("Scan")):
            resp = call(make_event("GET"))
        assert resp["statusCode"] == 500


# ---------------------------------------------------------------------------
# get_user  GET /users/{userid}
# ---------------------------------------------------------------------------

class TestGetUser:
    def test_existing_user(self, ddb_table):
        user = seed_user(ddb_table)
        resp = call(make_event("GET", userid=user["userid"]))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["userid"] == user["userid"]
        assert resp["parsed"]["email"] == user["email"]

    def test_not_found(self, ddb_table):
        resp = call(make_event("GET", userid="does-not-exist"))
        assert resp["statusCode"] == 404

    def test_missing_userid_param(self, ddb_table):
        # pathParameters=None → get_user_id returns None → routed to list_users
        resp = call(make_event("GET", userid=None))
        assert resp["statusCode"] == 200
        assert "users" in resp["parsed"]

    def test_dynamodb_error_returns_500(self, ddb_table):
        with patch.object(lambda_function.table, "get_item", side_effect=client_error("GetItem")):
            resp = call(make_event("GET", userid="u1"))
        assert resp["statusCode"] == 500


# ---------------------------------------------------------------------------
# create_user  POST /users
# ---------------------------------------------------------------------------

class TestCreateUser:
    VALID_BODY = {"first_name": "Ada", "last_name": "Lovelace", "email": "Ada@Example.COM"}

    def test_creates_user_returns_201(self, ddb_table):
        resp = call(make_event("POST", body=self.VALID_BODY))
        assert resp["statusCode"] == 201

    def test_auto_generates_userid(self, ddb_table):
        resp = call(make_event("POST", body=self.VALID_BODY))
        assert "userid" in resp["parsed"]
        assert resp["parsed"]["userid"]  # non-empty

    def test_email_is_lowercased(self, ddb_table):
        resp = call(make_event("POST", body=self.VALID_BODY))
        assert resp["parsed"]["email"] == "ada@example.com"

    def test_item_persisted_in_table(self, ddb_table):
        resp = call(make_event("POST", body=self.VALID_BODY))
        userid = resp["parsed"]["userid"]
        item = ddb_table.get_item(Key={"userid": userid})["Item"]
        assert item["first_name"] == "Ada"

    def test_missing_email_returns_400(self, ddb_table):
        body = {"first_name": "Ada", "last_name": "Lovelace"}
        resp = call(make_event("POST", body=body))
        assert resp["statusCode"] == 400

    def test_missing_first_name_returns_400(self, ddb_table):
        body = {"last_name": "Lovelace", "email": "ada@example.com"}
        resp = call(make_event("POST", body=body))
        assert resp["statusCode"] == 400

    def test_missing_last_name_returns_400(self, ddb_table):
        body = {"first_name": "Ada", "email": "ada@example.com"}
        resp = call(make_event("POST", body=body))
        assert resp["statusCode"] == 400

    def test_invalid_json_returns_400(self, ddb_table):
        event = make_event("POST")
        event["body"] = "not-json"
        resp = call(event)
        assert resp["statusCode"] == 400

    def test_none_body_returns_400(self, ddb_table):
        resp = call(make_event("POST", body=None))
        assert resp["statusCode"] == 400

    def test_dynamodb_error_returns_500(self, ddb_table):
        with patch.object(lambda_function.table, "put_item", side_effect=client_error("PutItem")):
            resp = call(make_event("POST", body=self.VALID_BODY))
        assert resp["statusCode"] == 500


# ---------------------------------------------------------------------------
# update_user  PUT /users/{userid}
# ---------------------------------------------------------------------------

class TestUpdateUser:
    def test_update_single_field(self, ddb_table):
        user = seed_user(ddb_table)
        resp = call(make_event("PUT", userid=user["userid"], body={"email": "new@example.com"}))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["email"] == "new@example.com"

    def test_update_all_fields(self, ddb_table):
        user = seed_user(ddb_table)
        updates = {"first_name": "New", "last_name": "Name", "email": "new@example.com"}
        resp = call(make_event("PUT", userid=user["userid"], body=updates))
        assert resp["statusCode"] == 200
        assert resp["parsed"]["first_name"] == "New"
        assert resp["parsed"]["last_name"] == "Name"

    def test_user_not_found_returns_404(self, ddb_table):
        resp = call(make_event("PUT", userid="ghost", body={"email": "x@x.com"}))
        assert resp["statusCode"] == 404

    def test_no_valid_fields_returns_400(self, ddb_table):
        user = seed_user(ddb_table)
        resp = call(make_event("PUT", userid=user["userid"], body={"unknown_field": "value"}))
        assert resp["statusCode"] == 400

    def test_invalid_json_returns_400(self, ddb_table):
        event = make_event("PUT", userid="u1")
        event["body"] = "bad-json"
        resp = call(event)
        assert resp["statusCode"] == 400

    def test_dynamodb_update_error_returns_500(self, ddb_table):
        user = seed_user(ddb_table)
        with patch.object(lambda_function.table, "update_item", side_effect=client_error("UpdateItem")):
            resp = call(make_event("PUT", userid=user["userid"], body={"email": "x@x.com"}))
        assert resp["statusCode"] == 500


# ---------------------------------------------------------------------------
# delete_user  DELETE /users/{userid}
# ---------------------------------------------------------------------------

class TestDeleteUser:
    def test_existing_user_deleted(self, ddb_table):
        user = seed_user(ddb_table)
        resp = call(make_event("DELETE", userid=user["userid"]))
        assert resp["statusCode"] == 200
        # Verify actually removed
        result = ddb_table.get_item(Key={"userid": user["userid"]})
        assert "Item" not in result

    def test_user_not_found_returns_404(self, ddb_table):
        resp = call(make_event("DELETE", userid="ghost"))
        assert resp["statusCode"] == 404

    def test_dynamodb_delete_error_returns_500(self, ddb_table):
        user = seed_user(ddb_table)
        with patch.object(lambda_function.table, "delete_item", side_effect=client_error("DeleteItem")):
            resp = call(make_event("DELETE", userid=user["userid"]))
        assert resp["statusCode"] == 500


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

class TestHandlerDispatch:
    def test_unknown_method_returns_405(self, ddb_table):
        resp = call(make_event("PATCH"))
        assert resp["statusCode"] == 405

    def test_options_returns_200(self, ddb_table):
        resp = call(make_event("OPTIONS"))
        assert resp["statusCode"] == 200

    def test_v2_event_get_users(self, ddb_table):
        seed_user(ddb_table)
        resp = call(make_v2_event("GET"))
        assert resp["statusCode"] == 200
        assert "users" in resp["parsed"]

    def test_v2_event_create_user(self, ddb_table):
        body = {"first_name": "V2", "last_name": "Test", "email": "v2@test.com"}
        resp = call(make_v2_event("POST", body=body))
        assert resp["statusCode"] == 201
