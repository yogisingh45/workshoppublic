variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "workshop_stack_base_name" {
  description = "Base name for workshop stack resources"
  type        = string
  default     = "workshop"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "Workshop"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "Serverless Patterns"
}

variable "lambda_runtime" {
  description = "Lambda function runtime identifier"
  type        = string
  default     = "python3.10"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda function memory allocation in MB"
  type        = number
  default     = 256
}
