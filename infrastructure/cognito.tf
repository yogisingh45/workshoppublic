# ---------------------------------------------------------------------------
# Cognito User Pool
# ---------------------------------------------------------------------------
resource "aws_cognito_user_pool" "users" {
  name = "${var.workshop_stack_base_name}-user-pool"

  # Email is the username — no separate username field
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Self-registration enabled
  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Mark email as a required, mutable attribute
  schema {
    attribute_data_type = "String"
    name                = "email"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 3
      max_length = 255
    }
  }

  tags = {
    Name        = "${var.workshop_stack_base_name}-user-pool"
    Environment = var.environment
    Project     = var.project
  }
}

# ---------------------------------------------------------------------------
# App Client — no secret, public client for CLI / browser use
# ---------------------------------------------------------------------------
resource "aws_cognito_user_pool_client" "api" {
  name         = "${var.workshop_stack_base_name}_users_api_client"
  user_pool_id = aws_cognito_user_pool.users.id

  generate_secret = false

  refresh_token_validity = 30
  token_validity_units {
    refresh_token = "days"
  }

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
  ]

  callback_urls = ["http://localhost:3000/callback"]

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid"]
  supported_identity_providers         = ["COGNITO"]
}

# ---------------------------------------------------------------------------
# Hosted UI domain — prefix is unique per deployment (uses the client ID)
# ---------------------------------------------------------------------------
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.workshop_stack_base_name}-${aws_cognito_user_pool_client.api.id}"
  user_pool_id = aws_cognito_user_pool.users.id
}

# ---------------------------------------------------------------------------
# Administrators group
# ---------------------------------------------------------------------------
resource "aws_cognito_user_group" "admin_group" {
  name         = "Administrators"
  user_pool_id = aws_cognito_user_pool.users.id
  description  = "Workshop administrators"
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.users.id
}

output "cognito_user_pool_client_id" {
  description = "ID of the Cognito app client"
  value       = aws_cognito_user_pool_client.api.id
}

output "cognito_admin_group_name" {
  description = "Name of the Cognito Administrators group"
  value       = aws_cognito_user_group.admin_group.name
}

output "cognito_login_url" {
  description = "Hosted UI login URL"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com/login?client_id=${aws_cognito_user_pool_client.api.id}&response_type=code&scope=email+openid&redirect_uri=http://localhost:3000/callback"
}

output "cognito_auth_cli_command" {
  description = "Sample AWS CLI command to sign in and retrieve a JWT"
  value       = "aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH --client-id ${aws_cognito_user_pool_client.api.id} --auth-parameters USERNAME=<email>,PASSWORD=<password> --region ${var.region}"
}
