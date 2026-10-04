"""
conftest.py — path setup and shared fixtures for tests/unit/users/

Adds src/users to sys.path so that `import lambda_function` resolves
to /workshop/src/users/lambda_function.py without installing the package.

Why module-level env vars:
  lambda_function.py creates a boto3 DynamoDB resource at import time.
  Without a region in the environment, importing the module raises
  NoRegionError before any fixture can run. These defaults are overridden
  inside each test via the `ddb_table` fixture.
"""
import importlib
import json
import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# ── path setup ──────────────────────────────────────────────────────────────
USERS_SRC = str(Path(__file__).parents[3] / "src" / "users")
if USERS_SRC not in sys.path:
    sys.path.insert(0, USERS_SRC)

# ── environment defaults (must be set before lambda_function is imported) ───
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("USERS_TABLE_NAME", "test_users")

# ── constants ────────────────────────────────────────────────────────────────
TABLE_NAME = "test_users"


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def ddb_table(monkeypatch):
    """
    Spin up an in-memory DynamoDB table for one test, then tear it down.

    Calls importlib.reload(lambda_function) inside the mock_aws() context so
    that the module-level `table` object re-binds to the mocked resource.
    Tests that use this fixture always hit the in-memory table, never real AWS.
    """
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("USERS_TABLE_NAME", TABLE_NAME)

    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "userid", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userid", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # Reload so lambda_function.table points at the mocked resource.
        import lambda_function
        importlib.reload(lambda_function)
        yield table


# ── event builders ────────────────────────────────────────────────────────────

def make_event(method, userid=None, body=None):
    """API Gateway REST API (v1) proxy event."""
    return {
        "httpMethod": method,
        "pathParameters": {"userid": userid} if userid else None,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {},
    }


def make_v2_event(method, userid=None, body=None):
    """API Gateway HTTP API (v2) proxy event."""
    return {
        "pathParameters": {"userid": userid} if userid else None,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"http": {"method": method}},
    }


# ── data helpers ──────────────────────────────────────────────────────────────

def seed_user(table, **overrides):
    """Insert a user directly into the mocked table and return it."""
    user = {
        "userid": "test-uuid-1",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        **overrides,
    }
    table.put_item(Item=user)
    return user
