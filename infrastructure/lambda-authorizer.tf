locals {
  authorizer_src_dir   = "${path.module}/../src/authorizer"
  authorizer_build_dir = "${path.module}/../build/authorizer"
  authorizer_zip_path  = "${path.module}/../build/authorizer.zip"
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "authorizer" {
  name              = "/aws/lambda/${var.workshop_stack_base_name}_authorizer"
  retention_in_days = 30

  tags = {
    Name        = "${var.workshop_stack_base_name}_authorizer"
    Environment = var.environment
    Project     = var.project
  }
}

# ---------------------------------------------------------------------------
# IAM Role — CloudWatch Logs only; no data-plane permissions needed
# ---------------------------------------------------------------------------
resource "aws_iam_role" "authorizer" {
  name = "${var.workshop_stack_base_name}_authorizer_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "${var.workshop_stack_base_name}_authorizer_role"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "authorizer_basic_execution" {
  role       = aws_iam_role.authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---------------------------------------------------------------------------
# Build: pip-install python-jose into staging dir, then zip
# ---------------------------------------------------------------------------
resource "null_resource" "authorizer_build" {
  triggers = {
    source_hash       = filesha256("${local.authorizer_src_dir}/lambda_function.py")
    requirements_hash = filesha256("${local.authorizer_src_dir}/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      rm -rf "${local.authorizer_build_dir}"
      mkdir -p "${local.authorizer_build_dir}"
      cp "${local.authorizer_src_dir}/lambda_function.py" "${local.authorizer_build_dir}/"
      python3 -m pip install \
        -r "${local.authorizer_src_dir}/requirements.txt" \
        -t "${local.authorizer_build_dir}/" \
        --upgrade \
        --quiet
    EOT
  }
}

data "archive_file" "authorizer" {
  type        = "zip"
  source_dir  = local.authorizer_build_dir
  output_path = local.authorizer_zip_path
  depends_on  = [null_resource.authorizer_build]
}

# ---------------------------------------------------------------------------
# Lambda Function
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "authorizer" {
  function_name = "${var.workshop_stack_base_name}_authorizer"
  role          = aws_iam_role.authorizer.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.10"

  filename         = data.archive_file.authorizer.output_path
  source_code_hash = data.archive_file.authorizer.output_base64sha256

  memory_size = 128
  timeout     = 10

  environment {
    variables = {
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.users.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.api.id
      COGNITO_REGION       = var.region
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.authorizer,
    aws_iam_role_policy_attachment.authorizer_basic_execution,
  ]

  tags = {
    Name        = "${var.workshop_stack_base_name}_authorizer"
    Environment = var.environment
    Project     = var.project
  }
}

# ---------------------------------------------------------------------------
# API Gateway Authorizer
# ---------------------------------------------------------------------------
resource "aws_api_gateway_authorizer" "cognito_jwt" {
  name                             = "${var.workshop_stack_base_name}_cognito_jwt_authorizer"
  rest_api_id                      = aws_api_gateway_rest_api.users_api.id
  authorizer_uri                   = aws_lambda_function.authorizer.invoke_arn
  authorizer_result_ttl_in_seconds = 300
  identity_source                  = "method.request.header.Authorization"
  type                             = "TOKEN"
}

# ---------------------------------------------------------------------------
# Lambda permission — API Gateway may invoke the authorizer
# ---------------------------------------------------------------------------
resource "aws_lambda_permission" "authorizer_invoke" {
  statement_id  = "AllowAPIGatewayAuthorizerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.users_api.execution_arn}/authorizers/${aws_api_gateway_authorizer.cognito_jwt.id}"
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
output "authorizer_id" {
  description = "ID of the Cognito JWT Lambda authorizer"
  value       = aws_api_gateway_authorizer.cognito_jwt.id
}

output "authorizer_lambda_arn" {
  description = "ARN of the Lambda authorizer function"
  value       = aws_lambda_function.authorizer.arn
}
