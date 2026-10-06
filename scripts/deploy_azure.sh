#!/usr/bin/env bash
# Run in Azure Cloud Shell (Bash) or a shell with Azure CLI and Python 3.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  echo 'Usage: bash scripts/deploy_azure.sh RESOURCE_GROUP REGION SSH_PUBLIC_KEY [RELEASE_TAG]' >&2
  exit 2
fi
resource_group="$1"
location="$2"
public_key_file="$3"
release_tag="${4:-}"
test -f "$public_key_file" || { echo 'SSH public key file is missing.' >&2; exit 2; }
if ! head -c 20 "$public_key_file" | grep -qE '^ssh-(ed25519|rsa) '; then
  echo 'Supply an OpenSSH PUBLIC key file, not a private key.' >&2
  exit 2
fi
az account show --query '{subscription:name,id:id}' -o table
echo 'This creates credit-funded resources. Keep your Azure student spending limit enabled.'
if [ -z "$release_tag" ]; then
  release_tag="$(curl --fail --silent --show-error https://api.github.com/repos/Arnav-Dugad/imagevault-ai/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')"
fi
[[ "$release_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-build\.[0-9]+)?$ ]] || { echo 'Invalid release tag.' >&2; exit 2; }
curl --fail --silent --show-error --location --head "https://github.com/Arnav-Dugad/imagevault-ai/releases/download/$release_tag/imagevault-ai.tar.gz" > /dev/null
# Cloud Shell egress may differ from your laptop: use SSH_SOURCE_CIDR to override.
ssh_cidr="${SSH_SOURCE_CIDR:-$(curl --fail --silent --show-error https://api.ipify.org)/32}"
python3 -c 'import ipaddress,sys; n=ipaddress.ip_network(sys.argv[1], strict=False); assert n.version == 4 and n.prefixlen >= 24, "Use a restricted IPv4 CIDR (/24 or narrower)"' "$ssh_cidr"
az group create --name "$resource_group" --location "$location" -o none
az deployment group create --resource-group "$resource_group" --name imagevault \
  --template-file infra/azure/main.bicep \
  --parameters location="$location" sshPublicKey="$(cat "$public_key_file")" \
  sshSourceCidr="$ssh_cidr" releaseTag="$release_tag" vmSize="${AZURE_VM_SIZE:-Standard_B2ms}" \
  --query properties.outputs -o json
echo 'Wait for cloud-init and Docker builds to finish. See docs/azure-students.md for status and invite code.'
