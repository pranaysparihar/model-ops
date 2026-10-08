data "aws_availability_zones" "available" { state = "available" }
locals {
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
  tags = { "karpenter.sh/discovery" = var.cluster_name }
}
module "vpc" {
  source                                          = "terraform-aws-modules/vpc/aws"
  version                                         = "6.7.3"
  name                                            = var.cluster_name
  cidr                                            = "10.42.0.0/16"
  azs                                             = local.azs
  private_subnets                                 = ["10.42.0.0/20", "10.42.16.0/20"]
  public_subnets                                  = ["10.42.128.0/24", "10.42.129.0/24"]
  enable_nat_gateway                              = true
  single_nat_gateway                              = !var.ha_nat
  one_nat_gateway_per_az                          = var.ha_nat
  enable_dns_hostnames                            = true
  map_public_ip_on_launch                         = false
  enable_flow_log                                 = true
  create_flow_log_cloudwatch_iam_role             = true
  create_flow_log_cloudwatch_log_group            = true
  flow_log_cloudwatch_log_group_retention_in_days = 14
  private_subnet_tags                             = merge(local.tags, { "kubernetes.io/role/internal-elb" = "1" })
  public_subnet_tags                              = { "kubernetes.io/role/elb" = "1" }
}
module "eks" {
  source                                   = "terraform-aws-modules/eks/aws"
  version                                  = "21.29.0"
  name                                     = var.cluster_name
  kubernetes_version                       = var.kubernetes_version
  authentication_mode                      = "API"
  endpoint_private_access                  = true
  endpoint_public_access                   = length(var.admin_cidrs) > 0
  endpoint_public_access_cidrs             = var.admin_cidrs
  enable_cluster_creator_admin_permissions = false
  enabled_log_types                        = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days   = 14
  vpc_id                                   = module.vpc.vpc_id
  subnet_ids                               = module.vpc.private_subnets
  node_security_group_tags                 = local.tags
  access_entries = {
    operator = {
      principal_arn = var.admin_role_arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }
  addons = {
    coredns    = { addon_version = lookup(var.addon_versions, "coredns", null) }
    kube-proxy = { addon_version = lookup(var.addon_versions, "kube-proxy", null) }
    vpc-cni = {
      before_compute       = true
      addon_version        = lookup(var.addon_versions, "vpc-cni", null)
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
    eks-pod-identity-agent = {
      before_compute = true
      addon_version  = lookup(var.addon_versions, "eks-pod-identity-agent", null)
    }
    aws-ebs-csi-driver = {
      addon_version            = lookup(var.addon_versions, "aws-ebs-csi-driver", null)
      pod_identity_association = [{ role_arn = aws_iam_role.ebs.arn, service_account = "ebs-csi-controller-sa" }]
    }
  }
  eks_managed_node_groups = {
    system = {
      ami_type         = "AL2023_x86_64_STANDARD"
      instance_types   = ["m6i.large"]
      min_size         = 2
      max_size         = 3
      desired_size     = 2
      labels           = { "modelops.io/pool" = "system", "karpenter.sh/controller" = "true" }
      metadata_options = { http_endpoint = "enabled", http_tokens = "required", http_put_response_hop_limit = 1 }
    }
  }
}
module "karpenter" {
  source                          = "terraform-aws-modules/eks/aws//modules/karpenter"
  version                         = "21.29.0"
  cluster_name                    = module.eks.cluster_name
  namespace                       = "kube-system"
  service_account                 = "karpenter"
  create_pod_identity_association = true
  node_iam_role_use_name_prefix   = false
  node_iam_role_name              = "${var.cluster_name}-gpu-node"
  enable_spot_termination         = true
  node_iam_role_additional_policies = {
    ssm = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }
}
# S3 traffic stays on the AWS gateway endpoint rather than traversing NAT.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
}
resource "aws_budgets_budget" "lab" {
  count        = var.budget_email == "" ? 0 : 1
  name         = "${var.cluster_name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  # Account-wide by design: includes shared infrastructure and untagged spend.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
