# Useful KQL for the incident collector

Recent container errors:

```kusto
ContainerLogV2
| where TimeGenerated > ago(15m)
| where LogMessage has_any ("error", "exception", "failed", "panic")
| project TimeGenerated, PodName, ContainerName, LogMessage
| order by TimeGenerated desc
| take 100
```

Crash loop signals:

```kusto
KubePodInventory
| where TimeGenerated > ago(15m)
| where PodStatus in ("Failed", "Pending")
| project TimeGenerated, Namespace, PodName, PodStatus, ContainerStatusReason
| order by TimeGenerated desc
```
