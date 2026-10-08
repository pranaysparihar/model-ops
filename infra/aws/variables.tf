variable "region" {
  type    = string
  default = "us-east-1"
}
variable "environment" {
  type    = string
  default = "lab"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,16}$", var.environment))
    error_message = "Use a short lowercase environment name."
  }
}
variable "cluster_name" {
  type    = string
  default = "modelops-lab"
}
variable "kubernetes_version" {
  type    = string
  default = "1.35"
}
variable "admin_role_arn" {
  description = "Existing operator IAM role. No implicit creator-admin access."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:role/.+", var.admin_role_arn))
    error_message = "Supply an existing operator IAM role ARN."
  }
}
variable "admin_cidrs" {
  description = "Empty keeps the API private. Optional explicitly allowlisted public /32 operator addresses."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for cidr in var.admin_cidrs : can(cidrhost(cidr, 0)) && can(regex("^[0-9.]+/32$", cidr))])
    error_message = "Public API access is restricted to explicit IPv4 /32 addresses."
  }
}
variable "ha_nat" {
  description = "False uses one NAT gateway for the cost-conscious lab, an acknowledged AZ failure boundary."
  type        = bool
  default     = false
}
variable "addon_versions" {
  description = "Pin versions verified against your EKS version. Empty uses AWS-supported defaults, recorded in the plan."
  type        = map(string)
  default     = {}
}
variable "monthly_budget_usd" {
  type    = number
  default = 100
  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "Budget must be positive; it is an alert threshold, not a spending cap."
  }
}
variable "budget_email" {
  type    = string
  default = ""
}
