targetScope = 'resourceGroup'

@description('Azure region with student quota for the chosen VM SKU.')
param location string = resourceGroup().location

@description('Use an x64 VM with at least 8 GiB RAM. This consumes credit, not the tiny VM free allowance.')
param vmSize string = 'Standard_B2ms'

param adminUsername string = 'imagevault'

@description('SSH public key only; never pass a private key.')
param sshPublicKey string

@description('Your public IP as CIDR, e.g. 203.0.113.10/32. SSH is restricted to this range.')
param sshSourceCidr string

@description('Published GitHub release tag. The VM verifies its release archive checksum.')
param releaseTag string

@description('Daily automatic shutdown, in UTC. Deallocated disks and public IP still cost money.')
param shutdownTime string = '2000'

var suffix = uniqueString(resourceGroup().id)
var vmName = 'imagevault-vm'
var storageName = 'iv${suffix}'
var dnsLabel = 'imagevault-${suffix}'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'imagevault'
  properties: { publicAccess: 'None' }
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'imagevault-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'web'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRanges: ['80', '443']
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'ssh'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: sshSourceCidr
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'imagevault-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.42.0.0/16'] }
    subnets: [
      {
        name: 'app'
        properties: {
          addressPrefix: '10.42.0.0/24'
          networkSecurityGroup: { id: nsg.id }
        }
      }
    ]
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'imagevault-ip'
  location: location
  sku: { name: 'Standard' }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: { domainNameLabel: dnsLabel }
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: 'imagevault-nic'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'primary'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: { id: '${vnet.id}/subnets/app' }
          publicIPAddress: { id: publicIp.id }
        }
      }
    ]
  }
}

var domain = publicIp.properties.dnsSettings.fqdn
var cloudInit = replace(replace(replace(loadTextContent('cloud-init.yml'),
  '__APP_DOMAIN__', domain), '__STORAGE_ACCOUNT_URL__', storage.properties.primaryEndpoints.blob),
  '__RELEASE_TAG__', releaseTag)

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: 64
        managedDisk: { storageAccountType: 'StandardSSD_LRS' }
        deleteOption: 'Delete'
      }
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      customData: base64(cloudInit)
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: { publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: sshPublicKey }] }
      }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id }] }
  }
}

// Account scope is needed for user-delegation keys as well as blob read/write.
resource blobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, vm.id, 'blob-contributor')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: vm.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource shutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vmName}'
  location: location
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: { time: shutdownTime }
    timeZoneId: 'UTC'
    targetResourceId: vm.id
    notificationSettings: { status: 'Disabled', timeInMinutes: 30 }
  }
}

output appUrl string = 'https://${domain}'
output sshCommand string = 'ssh ${adminUsername}@${domain}'
output storageAccountUrl string = storage.properties.primaryEndpoints.blob
output vmResourceName string = vmName
