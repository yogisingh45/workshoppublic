# Design: Serverless Users Service

## Architecture Overview

```
Client
  │
  ▼
API Gateway (REST, v1)
  │  Authorization header
  ├──────────────────────▶ Lambda Authorizer ──▶ Cognito JWKS
  │  (on valid JWT)
  ▼
Lambda (CRUD) ──▶ DynamoDB Table
```

All resources are deployed to a single AWS region. Infrastructure is defined with Terraform.

## Components

### DynamoDB Table

- Partition key: `userid` (String)
- Billing mode: PAY_PER_REQUEST
- Table name should use a consistent prefix to avoid naming collisions

### Lambda: CRUD Function

- **Runtime**: Python 3.10
- **Environment**: `USERS_TABLE` (DynamoDB table name)
- **Permissions**: DynamoDB GetItem, PutItem, DeleteItem, Scan on the Users table
- **Route dispatch**: uses `httpMethod` and `resource` from the API Gateway event

### Lambda: Authorizer

- **Runtime**: Python 3.10
- **Environment**: `USER_POOL_ID`, `APPLICATION_CLIENT_ID`, `ADMIN_GROUP_NAME`
- **Type**: Token authorizer (reads `Authorization` header)
- **Caching**: JWKS public keys cached at module level (outside handler)

### API Gateway

- REST API defined with OpenAPI 3.0 body
- Stage name: `Prod`
- All endpoints use a Lambda token authorizer security scheme

#### Endpoints

| Method | Path | Integration |
|--------|------|-------------|
| GET | `/users` | Lambda proxy (CRUD function) |
| POST | `/users` | Lambda proxy (CRUD function) |
| GET | `/users/{userid}` | Lambda proxy (CRUD function) |
| PUT | `/users/{userid}` | Lambda proxy (CRUD function) |
| DELETE | `/users/{userid}` | Lambda proxy (CRUD function) |

### Cognito

- User Pool with email as username attribute
- User Pool Client with `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_USER_SRP_AUTH`,
  `ALLOW_REFRESH_TOKEN_AUTH`
- Admin group for role-based access

## Data Flow: Create User

```
1. Client → POST /users  (Authorization: Bearer <token>)
2. API Gateway → Lambda Authorizer (validate JWT)
3. Authorizer → Cognito JWKS endpoint (cold start only)
4. Authorizer → API Gateway (Allow policy)
5. API Gateway → Lambda CRUD (event with httpMethod=POST, resource=/users)
6. Lambda CRUD → DynamoDB PutItem (generates uuid, adds timestamp)
7. Lambda CRUD → API Gateway (200 + created user JSON)
8. API Gateway → Client (200 response)
```