variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "location" {
  type    = string
  default = "eastus2"
}

variable "resource_prefix" {
  type    = string
  default = "aks-sre"
}

variable "project_name" {
  type    = string
  default = "ai-sre"
}

variable "aks_kubernetes_version" {
  type    = string
  default = null
}

variable "openai_model_name" {
  type    = string
  default = "gpt-5.4-mini"
}

variable "openai_model_version" {
  type    = string
  default = "2026-03-17"
}

variable "tags" {
  type = map(string)
  default = {
    project     = "ai-aks-sre"
    environment = "lab"
    owner       = "portfolio"
  }
}
