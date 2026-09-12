# Security Notes

This lab deliberately keeps AI remediation non-autonomous.

Logs, alert payloads and Kubernetes events are treated as untrusted input because an attacker could place prompt-like text in a log line.

The analyser identity has access to the Azure OpenAI resource only. The collector identity has access to Log Analytics. Kubernetes event read access is namespace-scoped with a Role.

Do not expose the demo `/admin/failure-mode` endpoint or the collector over unrestricted public HTTP in production.

Use a private network path, authenticated webhook, API gateway, RBAC, TLS, durable incident storage and audit logging for a production deployment.
