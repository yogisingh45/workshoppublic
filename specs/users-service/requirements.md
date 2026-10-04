# Requirements: Serverless Users Service

## User Stories

### Requirement 1: User Record Management

**User Story:** As an API consumer, I want to create, read, update, and delete user
records so that I can manage user data programmatically through a consistent API.

#### Acceptance Criteria

1. WHEN a POST request is sent to `/users` with a valid JSON body, THE System SHALL create
   a new user record with a unique UUID as `userid` if one is not provided
2. WHEN a GET request is sent to `/users`, THE System SHALL return all user records from
   the database
3. WHEN a GET request is sent to `/users/{userid}`, THE System SHALL return the specific
   user record, or an empty object if not found
4. WHEN a PUT request is sent to `/users/{userid}`, THE System SHALL overwrite the user
   record with the provided JSON body, preserving the `userid`
5. WHEN a DELETE request is sent to `/users/{userid}`, THE System SHALL remove the user
   record from the database
6. THE System SHALL include a `timestamp` field (ISO 8601) on every created or updated record
7. ALL API responses SHALL include `Access-Control-Allow-Origin: *` header

### Requirement 2: Authentication

**User Story:** As a system administrator, I want all API endpoints protected by JWT
authentication so that only authorized users can access or modify user data.

#### Acceptance Criteria

1. THE Authentication_Service SHALL use Amazon Cognito as the identity provider
2. WHEN a request is made without a valid `Authorization` header, THE API SHALL return
   HTTP 401 Unauthorized
3. WHEN a valid JWT token is provided in the `Authorization` header, THE Authorizer SHALL
   verify the token signature using the Cognito JWKS endpoint
4. THE Authorizer SHALL cache the JWKS public keys during Lambda cold start to reduce
   latency on subsequent invocations
5. THE Cognito User Pool SHALL support email/password authentication
   (USER_PASSWORD_AUTH flow)

### Requirement 3: Data Storage

**User Story:** As a developer, I want user data stored in a managed NoSQL database so
that storage scales automatically without capacity planning.

#### Acceptance Criteria

1. THE System SHALL store user records in DynamoDB with `userid` (String) as partition key
2. THE DynamoDB table SHALL use PAY_PER_REQUEST billing mode
3. THE System SHALL support storing arbitrary JSON fields alongside the required `userid`
   and `timestamp` fields