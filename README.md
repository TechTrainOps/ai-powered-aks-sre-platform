# AI-Powered AKS SRE & Incident Automation Platform

An AI-assisted Site Reliability Engineering platform built on **Azure Kubernetes Service (AKS)** that detects application incidents, collects Kubernetes evidence, generates an AI-assisted root cause analysis, requires human approval, and executes controlled remediation runbooks.

The platform combines **Terraform, Azure DevOps, AKS, Helm, Azure Container Registry, Managed Prometheus, Azure Managed Grafana, Azure Monitor, Azure OpenAI, Kubernetes APIs, and Azure Blob Storage** into an end-to-end incident response workflow.

---

## Overview

Traditional monitoring systems can detect that an application is failing, but engineers still need to investigate the problem, determine the likely cause, choose a remediation action, execute it, and verify recovery.

This project automates that workflow while keeping remediation behind a **human approval gate**.

```text
                    +------------------+
                    |    Developer     |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Azure DevOps     |
                    | CI/CD Pipeline   |
                    +--------+---------+
                             |
             +---------------+---------------+
             |               |               |
             v               v               v
        Terraform        Application      Helm
        Validation          Tests        Validation
             |               |               |
             +---------------+---------------+
                             |
                             v
                    +------------------+
                    | Container Build   |
                    | & Security Scan   |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Azure Container   |
                    | Registry (ACR)    |
                    +--------+---------+
                             |
                             v
                  +------------------------+
                  |          AKS           |
                  |                        |
                  |  +------------------+  |
                  |  |     sre-api      |  |
                  |  |    FastAPI       |  |
                  |  +------------------+  |
                  |                        |
                  |  +------------------+  |
                  |  | Incident         |  |
                  |  | Collector        |  |
                  |  +------------------+  |
                  |                        |
                  |  +------------------+  |
                  |  |   AI Analyser    |  |
                  |  +------------------+  |
                  +-----------+------------+
                              |
                              v
                    +----------------------+
                    | Managed Prometheus   |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Azure Managed        |
                    | Grafana              |
                    +----------------------+

                               |
                               v
                    +----------------------+
                    | Azure Monitor Alert  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Incident Collector   |
                    +----------+-----------+
                               |
                +--------------+--------------+
                |              |              |
                v              v              v
              Pods          Logs           K8s Events
                |              |              |
                +--------------+--------------+
                               |
                               v
                    +----------------------+
                    | Azure OpenAI         |
                    | AI-assisted RCA      |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Human Approval       |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Remediation Runbook  |
                    +----------+-----------+
                               |
                 +-------------+-------------+
                 |             |             |
                 v             v             v
              Restart        Scale        Rollback
                 |             |             |
                 +-------------+-------------+
                               |
                               v
                    +----------------------+
                    | Health Verification  |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Azure Blob Storage    |
                    | Incident Record       |
                    +----------------------+