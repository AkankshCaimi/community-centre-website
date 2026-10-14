// The demonstration site on Azure. Spec: docs/specs/deploy.md (Z1 to Z8).
// Deployed into one resource group; see infra/README.md for the commands.

@description('Region for every resource.')
param location string = resourceGroup().location

@description('false on the very first run, when the registry does not hold an image yet.')
param deployApps bool = true

@description('Tag of the image community-centre:<tag> in the registry. Needed when deployApps is true.')
param imageTag string = ''

@secure()
@description('Password of the database administrator. Letters and digits only, so it needs no escaping in the connection string.')
param dbPassword string

@secure()
@description('SECRET_KEY of the application.')
param secretKey string

@secure()
@description('Address that receives the team notification for each booking request.')
param teamEmail string

@description('Address that receives the budget alerts.')
param alertEmail string

@description('Monthly budget, in the billing currency of the subscription.')
param budgetAmount int = 25

@description('false for a subscription that does not support budgets.')
param deployBudget bool = true

@description('First day of the current month; a budget must start on the first of a month.')
param budgetStart string = '${utcNow('yyyy-MM')}-01'

var suffix = uniqueString(resourceGroup().id)
var databaseName = 'community_centre'
var databaseAdmin = 'ccadmin'
var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var image = '${registry.properties.loginServer}/community-centre:${imageTag}'
var databaseUrl = 'postgresql://${databaseAdmin}:${dbPassword}@${database.properties.fullyQualifiedDomainName}:5432/${databaseName}?sslmode=require'

// Z7: held as Container Apps secrets, referenced by name from the settings below.
var secrets = [
  { name: 'database-url', value: databaseUrl }
  { name: 'secret-key', value: secretKey }
  { name: 'team-email', value: teamEmail }
]
var settings = [
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'SECRET_KEY', secretRef: 'secret-key' }
  { name: 'TEAM_EMAIL', secretRef: 'team-email' }
  // Azure's ingress is the one proxy in front of the application (F01 L6).
  { name: 'TRUSTED_PROXY_HOPS', value: '1' }
]
var registries = [
  { server: registry.properties.loginServer, identity: pullIdentity.id }
]
var size = { cpu: json('0.25'), memory: '0.5Gi' }
var healthProbe = { httpGet: { path: '/health', port: 8000 } }

// Z4: the two hourly jobs (times in UTC) and the one started by hand.
var jobs = [
  { name: 'job-auto-decline', command: 'auto-decline', schedule: '0 * * * *' }
  { name: 'job-purge', command: 'purge', schedule: '30 * * * *' }
  { name: 'job-init-db', command: 'init-db', schedule: '' }
]

// Z6
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-community-centre'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// Z5
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'crcc${suffix}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-community-centre-pull'
  location: location
}

resource pullAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, pullIdentity.id, acrPullRole)
  scope: registry
  properties: {
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
  }
}

// Z3
resource database 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'psql-cc-${suffix}'
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: databaseAdmin
    administratorLoginPassword: dbPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
  }

  resource appDatabase 'databases' = {
    name: databaseName
    properties: { charset: 'UTF8', collation: 'en_US.utf8' }
  }

  // The range 0.0.0.0 to 0.0.0.0 means "Azure services only".
  resource azureOnly 'firewallRules' = {
    name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
    properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
  }
}

// Z9: a workspace environment. The mode is set explicitly: left out, Azure created
// an express environment, and express environments do not support jobs.
resource environment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: 'cae-community-centre'
  location: location
  properties: {
    environmentMode: 'WorkloadProfiles'
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// Z1, Z2
resource website 'Microsoft.App/containerApps@2026-07-01' = if (deployApps) {
  name: 'ca-community-centre'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${pullIdentity.id}': {} }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'web'
          image: image
          resources: size
          env: settings
          probes: [
            union(healthProbe, { type: 'Startup', periodSeconds: 5, failureThreshold: 12 })
            union(healthProbe, { type: 'Liveness', periodSeconds: 30, failureThreshold: 3 })
            union(healthProbe, { type: 'Readiness', periodSeconds: 10, failureThreshold: 3 })
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 1 }
    }
  }
  dependsOn: [pullAccess, database::appDatabase, database::azureOnly]
}

// Z4
resource scheduled 'Microsoft.App/jobs@2026-07-01' = [
  for job in jobs: if (deployApps) {
    name: job.name
    location: location
    identity: {
      type: 'UserAssigned'
      userAssignedIdentities: { '${pullIdentity.id}': {} }
    }
    properties: {
      environmentId: environment.id
      workloadProfileName: 'Consumption'
      configuration: {
        triggerType: empty(job.schedule) ? 'Manual' : 'Schedule'
        replicaTimeout: 300
        replicaRetryLimit: 1
        scheduleTriggerConfig: empty(job.schedule)
          ? null
          : { cronExpression: job.schedule, parallelism: 1, replicaCompletionCount: 1 }
        manualTriggerConfig: empty(job.schedule) ? { parallelism: 1, replicaCompletionCount: 1 } : null
        registries: registries
        secrets: secrets
      }
      template: {
        containers: [
          {
            name: job.command
            image: image
            command: ['flask', '--app', 'app', job.command]
            resources: size
            env: settings
          }
        ]
      }
    }
    dependsOn: [pullAccess, database::appDatabase, database::azureOnly]
  }
]

// Z8
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = if (deployBudget) {
  name: 'budget-community-centre'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStart }
    notifications: {
      actual50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [alertEmail]
      }
      actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [alertEmail]
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [alertEmail]
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [alertEmail]
      }
    }
  }
}

// No secret is among the outputs (Z7).
output registryName string = registry.name
output databaseServer string = database.name
output siteAddress string = deployApps ? 'https://${website!.properties.configuration.ingress.fqdn}' : ''
