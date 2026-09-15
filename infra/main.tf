data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

locals {
  suffix                  = random_string.suffix.result
  rg_name                 = "rg-${var.resource_prefix}-${local.suffix}"
  vnet_name               = "vnet-${var.resource_prefix}"
  snet_name               = "snet-aks"
  aks_name                = "aks-${var.resource_prefix}-${local.suffix}"
  acr_name                = replace("acr${var.resource_prefix}${local.suffix}", "-", "")
  law_name                = "law-${var.resource_prefix}-${local.suffix}"
  amw_name                = "amw-${var.resource_prefix}-${local.suffix}"
  grafana_name            = "grafana-${var.resource_prefix}-${local.suffix}"
  openai_name             = "aoai-${var.resource_prefix}-${local.suffix}"
  identity_name           = "id-${var.project_name}-analyser"
  collector_identity_name = "id-${var.project_name}-collector"
}

resource "azurerm_resource_group" "main" {
  name     = local.rg_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_virtual_network" "main" {
  name                = local.vnet_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.42.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "aks" {
  name                 = local.snet_name
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.42.0.0/22"]
}

resource "azurerm_container_registry" "acr" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = local.law_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_monitor_workspace" "amw" {
  name                = local.amw_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_dashboard_grafana" "grafana" {
  name                = local.grafana_name
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  grafana_major_version             = 12
  api_key_enabled                   = false
  deterministic_outbound_ip_enabled = true
  public_network_access_enabled     = true

  identity {
    type = "SystemAssigned"
  }

  azure_monitor_workspace_integrations {
    resource_id = azurerm_monitor_workspace.amw.id
  }

  tags = var.tags
}

resource "azurerm_cognitive_account" "openai" {
  name                          = local.openai_name
  location                      = var.location
  resource_group_name           = azurerm_resource_group.main.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = local.openai_name
  public_network_access_enabled = true
  local_auth_enabled            = false
  identity {
    type = "SystemAssigned"
  }
  tags = var.tags
}

resource "azurerm_user_assigned_identity" "analyser" {
  name                = local.identity_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "collector" {
  name                = local.collector_identity_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_kubernetes_cluster" "aks" {
  name                = local.aks_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = local.aks_name
  kubernetes_version  = var.aks_kubernetes_version

  monitor_metrics {
    annotations_allowed = null
    labels_allowed      = null
  }

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  default_node_pool {
    name            = "system"
    vm_size         = "Standard_D4ds_v6"
    node_count      = 2
    os_disk_size_gb = 80
    vnet_subnet_id  = azurerm_subnet.aks.id
    type            = "VirtualMachineScaleSets"

    upgrade_settings {
      drain_timeout_in_minutes      = 0
      max_surge                     = "10%"
      node_soak_duration_in_minutes = 0
    }
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "azure"
    outbound_type       = "loadBalancer"
  }

  azure_policy_enabled = true

  microsoft_defender {
    log_analytics_workspace_id = "/subscriptions/2d1634f0-7a97-4b55-b237-f5b12e52c45c/resourceGroups/DefaultResourceGroup-EUS2/providers/Microsoft.OperationalInsights/workspaces/DefaultWorkspace-2d1634f0-7a97-4b55-b237-f5b12e52c45c-EUS2"
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "grafana_metrics_reader" {
  scope                = azurerm_monitor_workspace.amw.id
  role_definition_name = "Monitoring Data Reader"
  principal_id         = azurerm_dashboard_grafana.grafana.identity[0].principal_id
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

resource "azurerm_role_assignment" "logs_reader" {
  scope                = azurerm_log_analytics_workspace.law.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
}

resource "azurerm_role_assignment" "openai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.analyser.principal_id
}

resource "azurerm_federated_identity_credential" "collector" {
  name = "fic-ai-collector"

  user_assigned_identity_id = azurerm_user_assigned_identity.collector.id

  audience = ["api://AzureADTokenExchange"]
  issuer   = azurerm_kubernetes_cluster.aks.oidc_issuer_url
  subject  = "system:serviceaccount:sre:incident-collector"
}

resource "azurerm_federated_identity_credential" "analyser" {
  name = "fic-ai-analyser"

  user_assigned_identity_id = azurerm_user_assigned_identity.analyser.id

  audience = ["api://AzureADTokenExchange"]
  issuer   = azurerm_kubernetes_cluster.aks.oidc_issuer_url
  subject  = "system:serviceaccount:sre:ai-analyser"
}

resource "azurerm_cognitive_deployment" "openai_model" {
  name                 = var.openai_model_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = 1
  }

  version_upgrade_option = "NoAutoUpgrade"
}


resource "azurerm_storage_account" "incident_storage" {
  name                     = "staiakssreinc2026"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version = "TLS1_2"

  allow_nested_items_to_be_public = false

  public_network_access_enabled = true

  blob_properties {
    versioning_enabled = true
  }

  tags = {
    project = "ai-aks-sre"
    purpose = "incident-storage"
  }
}

resource "azurerm_storage_container" "incidents" {
  name                  = "incidents"
  storage_account_id    = azurerm_storage_account.incident_storage.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "collector_incident_storage" {
  scope                = azurerm_storage_account.incident_storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.collector.principal_id
}