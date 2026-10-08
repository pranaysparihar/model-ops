data "aws_iam_policy_document" "pod_identity" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "ebs" {
  name               = "${var.cluster_name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.pod_identity.json
}
resource "aws_iam_role_policy_attachment" "ebs" {
  role       = aws_iam_role.ebs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}
# Metadata only; the actual key is inserted outside Terraform so it never enters state.
resource "aws_secretsmanager_secret" "gateway" {
  name                    = "${var.cluster_name}/gateway-api-key"
  recovery_window_in_days = 7
}
resource "aws_iam_role" "external_secrets" {
  name               = "${var.cluster_name}-external-secrets"
  assume_role_policy = data.aws_iam_policy_document.pod_identity.json
}
resource "aws_iam_role_policy" "external_secrets" {
  role   = aws_iam_role.external_secrets.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"], Resource = aws_secretsmanager_secret.gateway.arn }] })
}
resource "aws_eks_pod_identity_association" "external_secrets" {
  cluster_name    = module.eks.cluster_name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = aws_iam_role.external_secrets.arn
}
