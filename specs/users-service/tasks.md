# Tasks: Serverless Users Service

## Task 1: Infrastructure Foundation

- [x] 1.1 Create Terraform provider configuration and data sources for region and account ID
- [x] 1.2 Define variables for resource naming prefix, Lambda runtime, timeout, and memory
- [x] 1.3 Create DynamoDB table resource (PAY_PER_REQUEST, `userid` partition key)
- [x] 1.4 Run `terraform init` and `terraform apply` to create the DynamoDB table
- [x] 1.5 Verify the table exists using the AWS CLI

## Task 2: Business Logic (CRUD Lambda)

- [x] 2.1 Create the Lambda function source with route-based CRUD handler
        (GET/POST /users, GET/PUT/DELETE /users/{userid})
- [x] 2.2 Create an IAM role with DynamoDB access policy for the Lambda
- [x] 2.3 Create the Terraform resources for packaging and deploying the Lambda
- [x] 2.4 Run `terraform apply` and verify the Lambda appears in AWS
- [x] 2.5 Test the Lambda manually with a test event

## Task 3: API Gateway

- [x] 3.1 Create REST API using OpenAPI 3.0 body with all five endpoints
- [x] 3.2 Add deployment, stage, and Lambda invoke permission
- [x] 3.3 Add CloudWatch logging for access logs
- [x] 3.4 Run `terraform apply` and note the API endpoint URL
- [x] 3.5 Test with `curl` (expect 403, authorizer not yet configured)

## Task 4: Authentication

- [x] 4.1 Create Cognito User Pool, Client, Domain, and admin group
- [x] 4.2 Create the Lambda authorizer function with JWT validation against Cognito JWKS
- [x] 4.3 Create IAM role and Terraform resources for the authorizer Lambda
- [x] 4.4 Update API Gateway to wire the authorizer security scheme
- [x] 4.5 Run `terraform apply` and verify all resources deploy successfully

## Task 5: End-to-End Verification

- [x] 5.1 Create a test user in Cognito and retrieve a JWT token
- [x] 5.2 Call `GET /users` with the token (expect 200 and empty list)
- [x] 5.3 Call `POST /users` to create a user (expect 200 and the created record)
- [x] 5.4 Call `GET /users/{userid}` to retrieve the user (expect 200)
- [x] 5.5 Call `PUT /users/{userid}` to update the user (expect 200)
- [x] 5.6 Call `DELETE /users/{userid}` to delete the user (expect 200)

## Task 6: Unit Tests

- [x] 6.1 Create test directory structure
- [x] 6.2 Write unit tests for CRUD Lambda using `moto` for DynamoDB mocking
- [x] 6.3 Run `pytest tests/unit/` and verify all tests pass