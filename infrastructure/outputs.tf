output "dynamodb_users_table_arn" {
  description = "ARN of the DynamoDB users table"
  value       = aws_dynamodb_table.users_table.arn
}

output "dynamodb_users_table_id" {
  description = "ID of the DynamoDB users table"
  value       = aws_dynamodb_table.users_table.id
}

output "dynamodb_users_table_name" {
  description = "Name of the DynamoDB users table"
  value       = aws_dynamodb_table.users_table.name
}
