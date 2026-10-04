terraform {
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

locals {
  lambda_src_dir   = "${path.module}/../src/users"
  lambda_build_dir = "${path.module}/../build/users"
  lambda_zip_path  = "${path.module}/../build/users.zip"
}

# ---------------------------------------------------------------------------
# Build: copy source + pip-install deps into a staging directory, then zip.
# Rebuilds whenever lambda_function.py or requirements.txt changes.
# ---------------------------------------------------------------------------
resource "null_resource" "users_lambda_build" {
  triggers = {
    source_hash       = filesha256("${local.lambda_src_dir}/lambda_function.py")
    requirements_hash = filesha256("${local.lambda_src_dir}/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      rm -rf "${local.lambda_build_dir}"
      mkdir -p "${local.lambda_build_dir}"
      cp "${local.lambda_src_dir}/lambda_function.py" "${local.lambda_build_dir}/"
      python3 -m pip install \
        -r "${local.lambda_src_dir}/requirements.txt" \
        -t "${local.lambda_build_dir}/" \
        --upgrade \
        --quiet
    EOT
  }
}

data "archive_file" "users_lambda" {
  type        = "zip"
  source_dir  = local.lambda_build_dir
  output_path = local.lambda_zip_path
  depends_on  = [null_resource.users_lambda_build]
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group — must exist before the function so Terraform manages
# retention rather than letting Lambda auto-create an unmanaged group.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "users_lambda" {
  name              = "/aws/lambda/${var.workshop_stack_base_name}_users_api"
  retention_in_days = 30

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api"
    Environment = var.environment
    Project     = var.project
  }
}

# ---------------------------------------------------------------------------
# IAM — least-privilege role for the Lambda
# ---------------------------------------------------------------------------
resource "aws_iam_role" "users_lambda" {
  name = "${var.workshop_stack_base_name}_users_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_lambda_role"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "users_lambda_basic_execution" {
  role       = aws_iam_role.users_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "users_lambda_xray" {
  role       = aws_iam_role.users_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Scoped inline policy: CRUD on the users table only — no wildcards.
resource "aws_iam_role_policy" "users_lambda_dynamodb" {
  name = "${var.workshop_stack_base_name}_users_lambda_dynamodb"
  role = aws_iam_role.users_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "UserTableCRUD"
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
      ]
      Resource = aws_dynamodb_table.users_table.arn
    }]
  })
}

# ---------------------------------------------------------------------------
# Lambda function
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "users_api" {
  function_name = "${var.workshop_stack_base_name}_users_api"
  role          = aws_iam_role.users_lambda.arn
  handler       = "lambda_function.handler"
  runtime       = var.lambda_runtime

  filename         = data.archive_file.users_lambda.output_path
  source_code_hash = data.archive_file.users_lambda.output_base64sha256

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout

  environment {
    variables = {
      USERS_TABLE_NAME = aws_dynamodb_table.users_table.name
    }
  }

  tracing_config {
    mode = "Active"
  }

  # Ensure the log group and IAM role are ready before the function is created.
  depends_on = [
    aws_cloudwatch_log_group.users_lambda,
    aws_iam_role_policy_attachment.users_lambda_basic_execution,
  ]

  tags = {
    Name        = "${var.workshop_stack_base_name}_users_api"
    Environment = var.environment
    Project     = var.project
  }
}

# Allows any API Gateway in this account/region to invoke the function.
# Scoped to account + region to avoid granting cross-account access.
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.users_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:*"
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "users_lambda_arn" {
  description = "ARN of the users Lambda function"
  value       = aws_lambda_function.users_api.arn
}

output "users_lambda_function_name" {
  description = "Name of the users Lambda function"
  value       = aws_lambda_function.users_api.function_name
}

output "users_lambda_invoke_arn" {
  description = "Invoke ARN of the users Lambda function (used by API Gateway)"
  value       = aws_lambda_function.users_api.invoke_arn
}
