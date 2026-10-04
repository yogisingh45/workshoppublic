import importlib
import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Set fake AWS env vars at module level so `import lambda_function` at
# test-collection time doesn't raise NoRegionError. The ddb_table fixture
# reloads the module inside mock_aws() so all actual DynamoDB calls go to moto.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("USERS_TABLE_NAME", TABLE_NAME := "test_users")

@pytest.fixture
def ddb_table(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("USERS_TABLE_NAME", TABLE_NAME)

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "userid", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userid", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # Reload the module so its module-level `table` object re-binds
        # to the mocked DynamoDB resource instead of real AWS.
        import lambda_function
        importlib.reload(lambda_function)
        yield table


def make_event(method, userid=None, body=None):
    """Build an API Gateway REST API (v1) proxy event."""
    return {
        "httpMethod": method,
        "pathParameters": {"userid": userid} if userid else None,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {},
    }


def make_v2_event(method, userid=None, body=None):
    """Build an API Gateway HTTP API (v2) proxy event."""
    return {
        "pathParameters": {"userid": userid} if userid else None,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"http": {"method": method}},
    }


def seed_user(table, **overrides):
    """Insert a pre-built user into the mocked table and return it."""
    user = {
        "userid": "test-uuid-1",
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        **overrides,
    }
    table.put_item(Item=user)
    return user
