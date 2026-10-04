# Serverless Patterns Workshop Infrastructure

This directory contains Terraform configuration for the Serverless Patterns workshop.

## Overview

Provisions AWS infrastructure for the workshop environment using Terraform.

## Variables

| Name | Description | Default |
|------|-------------|---------|
| `region` | AWS region to deploy resources | `us-west-2` |
| `workshop_stack_base_name` | Base name for workshop stack resources | `workshop` |
| `environment` | Deployment environment | `Workshop` |
| `project` | Project name | `Serverless Patterns` |

## Usage

```bash
terraform init
terraform plan
terraform apply
```
