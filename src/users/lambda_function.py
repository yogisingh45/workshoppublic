import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["USERS_TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
}


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def get_method(event):
    # HTTP API v2
    http = event.get("requestContext", {}).get("http", {})
    if http:
        return http.get("method", "")
    # REST API v1
    return event.get("httpMethod", "")


def get_user_id(event):
    return (event.get("pathParameters") or {}).get("userid")


def parse_body(event):
    body = event.get("body") or "{}"
    try:
        return json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in request body")


def list_users():
    try:
        result = table.scan()
        return build_response(200, {"users": result.get("Items", [])})
    except ClientError as e:
        logger.error("DynamoDB scan failed: %s", e.response["Error"])
        return build_response(500, {"error": "Failed to list users"})


def get_user(user_id):
    try:
        result = table.get_item(Key={"userid": user_id})
        item = result.get("Item")
        if not item:
            return build_response(404, {"error": f"User {user_id} not found"})
        return build_response(200, item)
    except ClientError as e:
        logger.error("DynamoDB get_item failed for %s: %s", user_id, e.response["Error"])
        return build_response(500, {"error": "Failed to get user"})


def create_user(body):
    required = ["first_name", "last_name", "email"]
    missing = [f for f in required if not str(body.get(f, "")).strip()]
    if missing:
        return build_response(400, {"error": f"Missing required fields: {', '.join(missing)}"})

    user = {
        "userid": str(uuid.uuid4()),
        "first_name": str(body["first_name"]).strip(),
        "last_name": str(body["last_name"]).strip(),
        "email": str(body["email"]).strip().lower(),
    }

    try:
        table.put_item(Item=user)
        logger.info("Created user userid=%s", user["userid"])
        return build_response(201, user)
    except ClientError as e:
        logger.error("DynamoDB put_item failed: %s", e.response["Error"])
        return build_response(500, {"error": "Failed to create user"})


def update_user(user_id, body):
    allowed = {"first_name", "last_name", "email"}
    updates = {k: str(v).strip() for k, v in body.items() if k in allowed and str(v).strip()}
    if not updates:
        return build_response(400, {"error": f"Provide at least one of: {', '.join(sorted(allowed))}"})

    # Verify the user exists before updating
    try:
        if not table.get_item(Key={"userid": user_id}).get("Item"):
            return build_response(404, {"error": f"User {user_id} not found"})
    except ClientError as e:
        logger.error("DynamoDB get_item failed for %s: %s", user_id, e.response["Error"])
        return build_response(500, {"error": "Failed to update user"})

    # Build a safe update expression using attribute name placeholders to avoid
    # reserved word collisions (e.g. "name" is reserved in DynamoDB).
    expr_names = {f"#k{i}": k for i, k in enumerate(updates)}
    expr_values = {f":v{i}": v for i, v in enumerate(updates.values())}
    set_clause = ", ".join(f"{n} = {v}" for n, v in zip(expr_names, expr_values))

    try:
        result = table.update_item(
            Key={"userid": user_id},
            UpdateExpression=f"SET {set_clause}",
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        logger.info("Updated user userid=%s fields=%s", user_id, list(updates))
        return build_response(200, result["Attributes"])
    except ClientError as e:
        logger.error("DynamoDB update_item failed for %s: %s", user_id, e.response["Error"])
        return build_response(500, {"error": "Failed to update user"})


def delete_user(user_id):
    try:
        if not table.get_item(Key={"userid": user_id}).get("Item"):
            return build_response(404, {"error": f"User {user_id} not found"})
    except ClientError as e:
        logger.error("DynamoDB get_item failed for %s: %s", user_id, e.response["Error"])
        return build_response(500, {"error": "Failed to delete user"})

    try:
        table.delete_item(Key={"userid": user_id})
        logger.info("Deleted user userid=%s", user_id)
        return build_response(200, {"message": f"User {user_id} deleted"})
    except ClientError as e:
        logger.error("DynamoDB delete_item failed for %s: %s", user_id, e.response["Error"])
        return build_response(500, {"error": "Failed to delete user"})


def handler(event, context):
    # Log the event without the body to avoid logging PII
    safe_log = {k: v for k, v in event.items() if k != "body"}
    logger.info("Request: %s", json.dumps(safe_log))

    try:
        method = get_method(event)
        user_id = get_user_id(event)

        if method == "OPTIONS":
            return build_response(200, {})

        if method == "GET" and not user_id:
            return list_users()
        if method == "GET" and user_id:
            return get_user(user_id)
        if method == "POST":
            return create_user(parse_body(event))
        if method == "PUT" and user_id:
            return update_user(user_id, parse_body(event))
        if method == "DELETE" and user_id:
            return delete_user(user_id)

        return build_response(405, {"error": f"Method not allowed: {method}"})

    except ValueError as e:
        return build_response(400, {"error": str(e)})
    except Exception:
        logger.exception("Unhandled exception")
        return build_response(500, {"error": "Internal server error"})
