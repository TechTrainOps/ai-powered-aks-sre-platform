terraform {
  backend "azurerm" {
    resource_group_name  = "rg-ai-aks-sre-tfstate"
    storage_account_name = "staiakssre2026"
    container_name       = "tfstate"
    key                  = "ai-aks-sre.tfstate"

    use_azuread_auth = true
  }
}