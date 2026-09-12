output "resource_group_name" { value = azurerm_resource_group.main.name }
output "aks_name" { value = azurerm_kubernetes_cluster.aks.name }
output "acr_name" { value = azurerm_container_registry.acr.name }
output "acr_login_server" { value = azurerm_container_registry.acr.login_server }
output "acr_id" {
  description = "Azure Container Registry resource ID"
  value       = azurerm_container_registry.acr.id
}
output "log_analytics_workspace_id" { value = azurerm_log_analytics_workspace.law.id }
output "log_analytics_workspace_customer_id" { value = azurerm_log_analytics_workspace.law.workspace_id }
output "monitor_workspace_id" { value = azurerm_monitor_workspace.amw.id }
output "grafana_endpoint" { value = azurerm_dashboard_grafana.grafana.endpoint }
output "openai_endpoint" { value = azurerm_cognitive_account.openai.endpoint }
output "analyser_client_id" { value = azurerm_user_assigned_identity.analyser.client_id }
output "aks_oidc_issuer_url" { value = azurerm_kubernetes_cluster.aks.oidc_issuer_url }
output "openai_deployment_name" {
  description = "Azure OpenAI model deployment name"
  value       = azurerm_cognitive_deployment.openai_model.name
}
output "collector_client_id" {
  description = "Incident Collector managed identity client ID"
  value       = azurerm_user_assigned_identity.collector.client_id
}
