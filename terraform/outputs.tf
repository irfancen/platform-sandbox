output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}

output "app_role_arn" {
  value = aws_iam_role.app.arn
}

output "app_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}
