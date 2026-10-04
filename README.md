# AnyCompany Users Service

A serverless RESTful API for managing user records with JWT-based authentication, deployed to AWS using Terraform.

## Architecture

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

## Tech Stack

| Layer | Technology |
|-------|-----------|
| IaC | Terraform |
| Runtime | Python 3.10 |
| Compute | AWS Lambda |
| Database | Amazon DynamoDB (on-demand) |
| API | Amazon API Gateway REST API (v1) |
| Auth | Amazon Cognito + Lambda Token Authorizer |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | List all users |
| POST | `/users` | Create a user |
| GET | `/users/{userid}` | Get a user by ID |
| PUT | `/users/{userid}` | Update a user |
| DELETE | `/users/{userid}` | Delete a user |

All endpoints require a valid Cognito JWT in the `Authorization: Bearer <token>` header and an `x-api-key` header.

## Project Structure

```
├── infrastructure/       # Terraform (.tf files)
│   ├── provider.tf       # AWS provider and data sources
│   ├── variables.tf      # Input variables
│   ├── ddb.tf            # DynamoDB table
│   ├── users-lambda.tf   # CRUD Lambda + IAM role
│   ├── api-gateway.tf    # REST API, stage, usage plan
│   ├── cognito.tf        # User Pool, client, domain, group
│   ├── lambda-authorizer.tf  # JWT authorizer Lambda
│   └── outputs.tf        # Stack outputs
├── src/
│   ├── users/            # CRUD Lambda source
│   └── authorizer/       # JWT authorizer source
├── tests/
│   └── unit/users/       # Unit tests (moto)
└── specs/
    └── users-service/    # Requirements, design, tasks
```

## Getting Started

### Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0.0
- Python 3.10+

### Deploy

```bash
cd infrastructure
terraform init
terraform apply
```

### Run Unit Tests

```bash
python3 -m pytest tests/unit/ -v
```

### Get a JWT Token

```bash
# Create a user in Cognito
aws cognito-idp admin-create-user \
  --user-pool-id <pool-id> \
  --username user@example.com \
  --temporary-password "Temp1234!" \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <pool-id> \
  --username user@example.com \
  --password "YourPassword1!" \
  --permanent

# Authenticate
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id <client-id> \
  --auth-parameters USERNAME=user@example.com,PASSWORD="YourPassword1!"
```

### Call the API

```bash
curl -s \
  -H "Authorization: Bearer <token>" \
  -H "x-api-key: <api-key>" \
  https://<api-id>.execute-api.us-west-2.amazonaws.com/prod/users
```

## Outputs

After `terraform apply`, key values are printed:

| Output | Description |
|--------|-------------|
| `api_gateway_endpoint` | Base URL for the `/users` collection |
| `cognito_user_pool_id` | Cognito User Pool ID |
| `cognito_user_pool_client_id` | App client ID |
| `api_gateway_api_key` | API key (sensitive) |
