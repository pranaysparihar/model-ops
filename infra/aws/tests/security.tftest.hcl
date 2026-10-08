mock_provider "aws" {
  mock_data "aws_availability_zones" { defaults = { names = ["us-east-1a", "us-east-1b"] } }
  mock_data "aws_caller_identity" { defaults = { account_id = "123456789012", arn = "arn:aws:iam::123456789012:role/test", user_id = "test" } }
  mock_data "aws_partition" { defaults = { partition = "aws", dns_suffix = "amazonaws.com" } }
  mock_data "aws_region" { defaults = { name = "us-east-1", region = "us-east-1" } }
  mock_data "aws_iam_policy_document" { defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" } }
}
mock_provider "tls" {}
mock_provider "time" {}
mock_provider "null" {}
mock_provider "cloudinit" {}
override_resource {
  override_during = plan
  target          = aws_secretsmanager_secret.gateway
  values          = { arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:modelops-test" }
}
variables { admin_role_arn = "arn:aws:iam::123456789012:role/operator" }
run "private_defaults" {
  command = plan
  assert {
    condition     = jsondecode(aws_iam_role_policy.external_secrets.policy).Statement[0].Resource == "arn:aws:secretsmanager:us-east-1:123456789012:secret:modelops-test" && length(jsondecode(aws_iam_role_policy.external_secrets.policy).Statement[0].Action) == 2
    error_message = "External Secrets must read only the designated secret."
  }
  assert {
    condition     = length(var.admin_cidrs) == 0 && var.ha_nat == false
    error_message = "The lab must default to private API access and one NAT gateway."
  }
  assert {
    condition     = aws_secretsmanager_secret.gateway.recovery_window_in_days == 7
    error_message = "Secret deletion must be recoverable."
  }
  assert {
    condition     = aws_eks_pod_identity_association.external_secrets.namespace == "external-secrets" && aws_eks_pod_identity_association.external_secrets.service_account == "external-secrets"
    error_message = "Secret access must belong to the designated controller identity."
  }
  assert {
    condition     = length(aws_budgets_budget.lab) == 0
    error_message = "No budget notification should be created without a recipient."
  }
}
run "reject_public_internet" {
  command = plan
  variables { admin_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_user_as_operator" {
  command = plan
  override_resource {
    override_during = plan
    target          = aws_secretsmanager_secret.gateway
    values          = { arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:modelops-test" }
  }
  variables { admin_role_arn = "arn:aws:iam::123456789012:user/developer" }
  expect_failures = [var.admin_role_arn]
}
run "budget_is_opt_in" {
  command = plan
  variables { budget_email = "operator@example.com" }
  assert {
    condition     = length(aws_budgets_budget.lab) == 1 && aws_budgets_budget.lab[0].limit_amount == "100"
    error_message = "An explicit recipient must activate the configured budget alert."
  }
}
