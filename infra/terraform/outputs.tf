output "namespace" {
  value       = kubernetes_namespace_v1.imagevault.metadata[0].name
  description = "Namespace managed by Terraform."
}

output "local_services" {
  description = "NodePort URLs when Minikube maps NodePorts to localhost. Use `minikube service --url` otherwise."
  value = {
    imagevault = "http://localhost:30080"
    minio_api  = "http://localhost:30090"
    minio      = "http://localhost:30091"
    grafana    = "http://localhost:30001"
  }
}

output "scaling_demo" {
  value = "kubectl scale deployment imagevault-backend -n imagevault --replicas=3"
}
