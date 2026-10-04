# ---------------------------------------------------------------------------
# CloudWatch access log group for API Gateway
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.workshop_stack_base_name}_users_api"
  retention_in_days = 30

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api_gw_logs"
    Environment = var.environment
    Project     = var.project
  }
}

# Account-level IAM role allowing API Gateway to write execution logs to
# CloudWatch. This is a singleton per AWS account — it applies to all APIs.
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.workshop_stack_base_name}_api_gw_cloudwatch_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "apigateway.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "${var.workshop_stack_base_name}_api_gw_cloudwatch_role"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
  depends_on          = [aws_iam_role_policy_attachment.api_gateway_cloudwatch]
}

# ---------------------------------------------------------------------------
# REST API — regional endpoint
# ---------------------------------------------------------------------------
resource "aws_api_gateway_rest_api" "users_api" {
  name        = "${var.workshop_stack_base_name}_users_api"
  description = "Users CRUD REST API for the ${var.project} workshop"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api"
    Environment = var.environment
    Project     = var.project
  }
}

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
resource "aws_api_gateway_resource" "users" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  parent_id   = aws_api_gateway_rest_api.users_api.root_resource_id
  path_part   = "users"
}

resource "aws_api_gateway_resource" "user" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  parent_id   = aws_api_gateway_resource.users.id
  path_part   = "{userid}"
}

# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "get_users" {
  rest_api_id   = aws_api_gateway_rest_api.users_api.id
  resource_id   = aws_api_gateway_resource.users.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "get_users" {
  rest_api_id             = aws_api_gateway_rest_api.users_api.id
  resource_id             = aws_api_gateway_resource.users.id
  http_method             = aws_api_gateway_method.get_users.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.users_api.invoke_arn
}

# ---------------------------------------------------------------------------
# POST /users
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "post_users" {
  rest_api_id   = aws_api_gateway_rest_api.users_api.id
  resource_id   = aws_api_gateway_resource.users.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "post_users" {
  rest_api_id             = aws_api_gateway_rest_api.users_api.id
  resource_id             = aws_api_gateway_resource.users.id
  http_method             = aws_api_gateway_method.post_users.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.users_api.invoke_arn
}

# ---------------------------------------------------------------------------
# OPTIONS /users — CORS preflight (MOCK, no API key required)
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "options_users" {
  rest_api_id      = aws_api_gateway_rest_api.users_api.id
  resource_id      = aws_api_gateway_resource.users.id
  http_method      = "OPTIONS"
  authorization    = "NONE"
  api_key_required = false
}

resource "aws_api_gateway_integration" "options_users" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  resource_id = aws_api_gateway_resource.users.id
  http_method = aws_api_gateway_method.options_users.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_users_200" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  resource_id = aws_api_gateway_resource.users.id
  http_method = aws_api_gateway_method.options_users.http_method
  status_code = "200"

  response_models = { "application/json" = "Empty" }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_users_200" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  resource_id = aws_api_gateway_resource.users.id
  http_method = aws_api_gateway_method.options_users.http_method
  status_code = aws_api_gateway_method_response.options_users_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ---------------------------------------------------------------------------
# GET /users/{userid}
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "get_user" {
  rest_api_id   = aws_api_gateway_rest_api.users_api.id
  resource_id   = aws_api_gateway_resource.user.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "get_user" {
  rest_api_id             = aws_api_gateway_rest_api.users_api.id
  resource_id             = aws_api_gateway_resource.user.id
  http_method             = aws_api_gateway_method.get_user.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.users_api.invoke_arn
}

# ---------------------------------------------------------------------------
# PUT /users/{userid}
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "put_user" {
  rest_api_id   = aws_api_gateway_rest_api.users_api.id
  resource_id   = aws_api_gateway_resource.user.id
  http_method   = "PUT"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "put_user" {
  rest_api_id             = aws_api_gateway_rest_api.users_api.id
  resource_id             = aws_api_gateway_resource.user.id
  http_method             = aws_api_gateway_method.put_user.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.users_api.invoke_arn
}

# ---------------------------------------------------------------------------
# DELETE /users/{userid}
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "delete_user" {
  rest_api_id   = aws_api_gateway_rest_api.users_api.id
  resource_id   = aws_api_gateway_resource.user.id
  http_method   = "DELETE"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.cognito_jwt.id
  api_key_required = true
}

resource "aws_api_gateway_integration" "delete_user" {
  rest_api_id             = aws_api_gateway_rest_api.users_api.id
  resource_id             = aws_api_gateway_resource.user.id
  http_method             = aws_api_gateway_method.delete_user.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.users_api.invoke_arn
}

# ---------------------------------------------------------------------------
# OPTIONS /users/{userid} — CORS preflight (MOCK, no API key required)
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method" "options_user" {
  rest_api_id      = aws_api_gateway_rest_api.users_api.id
  resource_id      = aws_api_gateway_resource.user.id
  http_method      = "OPTIONS"
  authorization    = "NONE"
  api_key_required = false
}

resource "aws_api_gateway_integration" "options_user" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  resource_id = aws_api_gateway_resource.user.id
  http_method = aws_api_gateway_method.options_user.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "options_user_200" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  resource_id = aws_api_gateway_resource.user.id
  http_method = aws_api_gateway_method.options_user.http_method
  status_code = "200"

  response_models = { "application/json" = "Empty" }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_user_200" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  resource_id = aws_api_gateway_resource.user.id
  http_method = aws_api_gateway_method.options_user.http_method
  status_code = aws_api_gateway_method_response.options_user_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ---------------------------------------------------------------------------
# Deployment — triggers redeployment when any method or integration changes
# ---------------------------------------------------------------------------
resource "aws_api_gateway_deployment" "users_api" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.users,
      aws_api_gateway_resource.user,
      aws_api_gateway_method.get_users,
      aws_api_gateway_integration.get_users,
      aws_api_gateway_method.post_users,
      aws_api_gateway_integration.post_users,
      aws_api_gateway_method.options_users,
      aws_api_gateway_integration.options_users,
      aws_api_gateway_method.get_user,
      aws_api_gateway_integration.get_user,
      aws_api_gateway_method.put_user,
      aws_api_gateway_integration.put_user,
      aws_api_gateway_method.delete_user,
      aws_api_gateway_integration.delete_user,
      aws_api_gateway_method.options_user,
      aws_api_gateway_integration.options_user,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Stage: prod
# ---------------------------------------------------------------------------
resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.users_api.id
  deployment_id = aws_api_gateway_deployment.users_api.id
  stage_name    = "prod"

  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId          = "$context.requestId"
      ip                 = "$context.identity.sourceIp"
      requestTime        = "$context.requestTime"
      httpMethod         = "$context.httpMethod"
      resourcePath       = "$context.resourcePath"
      status             = "$context.status"
      responseLength     = "$context.responseLength"
      integrationLatency = "$context.integration.latency"
      errorMessage       = "$context.error.message"
    })
  }

  depends_on = [aws_api_gateway_account.main]

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api_prod"
    Environment = var.environment
    Project     = var.project
  }
}

# ---------------------------------------------------------------------------
# Method settings: metrics and throttling across all methods
# ---------------------------------------------------------------------------
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.users_api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = false  # enable only for debugging — logs full req/resp bodies

    throttling_rate_limit  = 100
    throttling_burst_limit = 200
  }
}

# ---------------------------------------------------------------------------
# API Key & Usage Plan
# ---------------------------------------------------------------------------
resource "aws_api_gateway_api_key" "users_api" {
  name        = "${var.workshop_stack_base_name}_users_api_key"
  description = "API key for ${var.project} users API"
  enabled     = true

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api_key"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_api_gateway_usage_plan" "users_api" {
  name        = "${var.workshop_stack_base_name}_users_api_usage_plan"
  description = "Usage plan for ${var.project} users API"

  api_stages {
    api_id = aws_api_gateway_rest_api.users_api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  throttle_settings {
    rate_limit  = 100
    burst_limit = 200
  }

  quota_settings {
    limit  = 10000
    period = "DAY"
  }

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api_usage_plan"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_api_gateway_usage_plan_key" "users_api" {
  key_id        = aws_api_gateway_api_key.users_api.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.users_api.id
}

# ---------------------------------------------------------------------------
# Lambda permission scoped to this REST API's execution ARN
# ---------------------------------------------------------------------------
resource "aws_lambda_permission" "rest_api_invoke" {
  statement_id  = "AllowRESTAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.users_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.users_api.execution_arn}/*/*"
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "api_gateway_endpoint" {
  description = "Base URL for the users collection endpoint"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/users"
}

output "api_gateway_execution_arn" {
  description = "Execution ARN of the REST API"
  value       = aws_api_gateway_rest_api.users_api.execution_arn
}

output "api_gateway_id" {
  description = "ID of the REST API"
  value       = aws_api_gateway_rest_api.users_api.id
}

output "api_gateway_api_key" {
  description = "API key value — required as x-api-key header on all CRUD requests"
  value       = aws_api_gateway_api_key.users_api.value
  sensitive   = true
}
