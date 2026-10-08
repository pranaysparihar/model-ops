output "cluster_name" { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "region" { value = var.region }
output "karpenter_node_role" { value = module.karpenter.node_iam_role_name }
output "interruption_queue" { value = module.karpenter.queue_name }
output "gateway_secret_arn" { value = aws_secretsmanager_secret.gateway.arn }
output "platform_values" {
  description = "Non-secret inputs consumed by the reviewed platform environment values file."
  value = {
    clusterName       = module.eks.cluster_name
    clusterEndpoint   = module.eks.cluster_endpoint
    region            = var.region
    nodeRole          = module.karpenter.node_iam_role_name
    interruptionQueue = module.karpenter.queue_name
    gatewaySecretArn  = aws_secretsmanager_secret.gateway.arn
  }
}
