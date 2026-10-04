import json
import logging
import os
import urllib.request

from jose import jwk, jwt
from jose.utils import base64url_decode

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ["COGNITO_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]

JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"

# Module-level cache — survives Lambda warm starts, avoids a JWKS fetch per request
_jwks_cache = None


def _get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        with urllib.request.urlopen(JWKS_URL) as resp:
            _jwks_cache = json.loads(resp.read())
        logger.info("JWKS fetched and cached (%d keys)", len(_jwks_cache.get("keys", [])))
    return _jwks_cache


def extract_token(event):
    auth_header = event.get("authorizationToken", "")
    if not auth_header.lower().startswith("bearer "):
        raise Exception("Unauthorized")
    token = auth_header[7:].strip()
    if not token:
        raise Exception("Unauthorized")
    return token


def verify_token(token):
    """Verify RS256 signature and required claims. Raises Exception('Unauthorized') on any failure."""
    try:
        headers = jwt.get_unverified_headers(token)
    except Exception:
        raise Exception("Unauthorized")

    kid = headers.get("kid")
    if not kid:
        raise Exception("Unauthorized")

    jwks = _get_jwks()
    matching_keys = [k for k in jwks.get("keys", []) if k.get("kid") == kid]
    if not matching_keys:
        # Kid not found — JWKS may have rotated; bust the cache and retry once
        global _jwks_cache
        _jwks_cache = None
        jwks = _get_jwks()
        matching_keys = [k for k in jwks.get("keys", []) if k.get("kid") == kid]
        if not matching_keys:
            raise Exception("Unauthorized")

    try:
        claims = jwt.decode(
            token,
            matching_keys[0],
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
            options={"verify_exp": True},
        )
    except Exception as e:
        logger.warning("JWT verification failed: %s", str(e))
        raise Exception("Unauthorized")

    if claims.get("token_use") != "id":
        logger.warning("Rejected token_use=%s (expected 'id')", claims.get("token_use"))
        raise Exception("Unauthorized")

    return claims


def build_policy(claims, method_arn):
    """Build an Allow policy scoped to the whole stage, with user claims in context."""
    # methodArn format: arn:aws:execute-api:{region}:{account}:{api-id}/{stage}/{method}/{resource}
    # Wildcard to stage level so the cached policy covers all methods
    parts = method_arn.split(":")
    gateway_parts = parts[5].split("/")
    stage_arn = ":".join(parts[:5]) + ":" + "/".join(gateway_parts[:2]) + "/*"

    return {
        "principalId": claims["sub"],
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Allow",
                "Resource": stage_arn,
            }],
        },
        "context": {
            "sub":    claims.get("sub", ""),
            "email":  claims.get("email", ""),
            "groups": json.dumps(claims.get("cognito:groups", [])),
        },
    }


def handler(event, context):
    logger.info("Authorizer invoked for methodArn=%s", event.get("methodArn"))
    token = extract_token(event)
    claims = verify_token(token)
    policy = build_policy(claims, event["methodArn"])
    logger.info("Authorized sub=%s email=%s", claims.get("sub"), claims.get("email"))
    return policy
