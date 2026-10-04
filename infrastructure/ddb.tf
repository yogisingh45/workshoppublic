resource "aws_dynamodb_table" "users_table" {
  name         = "${var.workshop_stack_base_name}_users"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "userid"

  attribute {
    name = "userid"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name        = "${var.workshop_stack_base_name}_users"
    Environment = var.environment
    Project     = var.project
  }
}
