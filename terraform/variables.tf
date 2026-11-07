variable "project" {
  type    = string
  default = "backend-api"
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "owner" {
  type    = string
  default = "platform-team"
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-3"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "kubernetes_version" {
  type    = string
  default = "1.36"
}

variable "node_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "node_count" {
  type    = number
  default = 2
}

variable "app_namespace" {
  type    = string
  default = "backend-api"
}

variable "app_service_account" {
  type    = string
  default = "backend-api"
}

variable "github_repo" {
  description = "GitHub repository (owner/name) allowed to assume the deploy role."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repo))
    error_message = "github_repo must be in owner/name form without wildcards."
  }
}
