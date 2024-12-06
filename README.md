# Datalake-brief

# Datalake partie 2 : Ingestion avancée, monitoring et sécurité 
## Contexte fictif 
En tant que **Data Ingénieur** au sein de l’entreprise **DataMoniSec**, vous êtes chargé de mettre en place une infrastructure de données robuste et sécurisée sur **Microsoft Azure**. Votre mission s’articule de la **sécurité** et du **monitoring** du data lake.

Votre mission est de :

- **Configurer** un Data Lake pour centraliser les données de l'entreprise.
- **Ingérer** des données provenant de différentes sources.
- Mettre en place des mesures de **sécurité** avancées pour protéger les données sensibles.
- Configurer **Azure Databricks** pour permettre à l'équipe Data Science d'analyser les données.
- Implémenter un système de **monitoring** et d'**alertes** pour surveiller l'infrastructure.
- [Bonus] : **Spark, terraform, pricing, ingestion avancée**

## Partie 1 : Veille 

### Storage Access Keys

Les **storage access keys** sont les clés générées automatiquement à la création d’un storage account et qui permettent un accès global au compte de stockage. 
On peut les visualiser dans la section Security + networking. 

![sak](images/sak.png)

 On les utilise en tant que credential pour se connecter au compte de stockage. 

![sak](images/sak2.png)

Avec Azure CLI on peut visualiser les clés : 
```bash
az storage account keys list \
    -- resource-group <resource-group> \
    -- account-name <storage-account>
```

Il est conseillé de regénérer régulièrement les clés (il est possible de créer une alerte en choisissant la fréquence souhaitée de rotation des clés) : 
- depuis le portail Azure 
- avec Azure CLI.

```bash
az storage account keys renew \
    -- resource-group <resource-group> \
    -- account-name <storage-account> \
    -- key primary 
```

### Shared Access Signatures 

Permet de contrôler l’accès aux données : à quelles données un utilisateur peut accéder, quelles autorisations il a, combien de temps il peut y accéder … sans transmettre les clés d’accès principales (storage access keys).

Le SAS est un token qu’on ajoute à l’URI de la ressource Azure Storage et qui permet l’accès aux données, tout en indiquant quel accès est donné.

On peut avoir SAS au niveau “compte” : Account SAS, qui offre un accès global à la ressource basé sur les clés du compte de stockage. 

On peut avoir un SAS au niveau “utilisateur” : User delegation SAS, qui est basée sur les identifiants Microsoft Entra ID. 

### Microsoft Entra ID 

Service de gestion des identités et des accès informatiques des utilisateurs. Permet de gérer les utilisateurs, les applications et les ressources dans un environnement sécurisé. Fournit des identités uniques pour accéder à des applications. Permet de contrôler l’accès sur la base de rôles spécifiques attribués aux utilisateurs.

### Azure Key Vault 

Stockage des secrets. Accès sécurisé aux secrets (ex: clé d’API, mots de passe, clé de chiffrement…). Il est possible d’accéder au key vault en utilisant les rôles définis dans Microsoft Entra ID.

Pour s’authentifier auprès des key vault : 
- identités managées 
- service princpal

### IAM et role-based access control (RBAC)

Système d’autorisation pour gérer l’accès aux ressources Azure. L’accès repose sur l’attribution de rôles aux utilisateurs, aux groupes, aux services principaux ou aux identités managées.
Le rôle doit concerner une étendue (scope) définie dès son attribution.

Sur la ressource dont on veut gérer les accès : 
- access control (IAM)
- role assignments 
- add role assignment 
- sélectionner le rôle souhaité 
- sélectionner les utilisateurs qui ont besoin de ce rôle (utilisateur, groupe, service principal…)

Il est possible de demander une activation par l’utilisateur avant qu’il puisse utiliser ce rôle, de définir une durée d’activation de ce rôle. Un rôle peut être mis à jour ultérieurement. 




## Partie 2 : Création et ingestion sécurisée sur le datalake 

Les ressources créées depuis le portail Azure sont : 
- un service principal secondaire : **keyvault-mplatteau**  (Microsoft Entra ID => app registration => new registration)
- un service principal : **dl-sas-read-mplatteau** (Microsoft Entra ID => app registration => new registration)
- un keyvault : **kv-mplatteau** (key vault => create => access configuration = vault access policy)
- un datalake : **adlsplatteau** 
- un container dans le datalake : **datastorage**

On ajoute ensuite des secrets aux services principaux (certificats & secrets => new client secret (il faut sauvegarder tout de suite le secret car ensuite il n’est plus affiché)).

On crée également un secret *sp-secret* dans le **Keyvault** pour stocker le secret du SP Principal.

Dans la configuration du datalake, le rôle de **Storage Blob Delegator** est attribué au service principal, ce qui lui permettra de créer des SAS Token. Toutefois, le SAS token généré ne va hériter que de ce rôle de Delegator, ce qui ne permet pas d'écrire dans le datalake. Il faut donc également ajouter le rôle **Storage Blob Data Contributor**. 
Finalement, le rôle **Storage Blob Data Contributor** est suffisant car il inclut beaucoup de droits. Si on utilise ce rôle, on peut écrire dans le Blob sans SAS. 

Donc ça fonctionne uniquement si on a le rôle **Storage Blob Data Contributor** : 
- avec le SAS, car il hérite de ce rôle Contributor ; 
- sans le SAS, car il n'est pas nécessaire, le rôle Contributor permet déjà d'écrire dans le blob.

![dl-role](images/dl-role.png)

Dans la configuration *Access Policies* du keyvault, les droits **get** sont attribués au service principal secondaire, ce qui lui permettra de lire le secret **sp-secret**. Celui-ci correspond au password du service principal. 

![kv-role](images/kv-role.png)

Le code dans le fichier **ingestion-datalake.py** permet de : 
- se connecter au keyvault à l'aide du service principal secondaire 
- récupérer le secret du service principal dans le key vault 
- utiliser le service principal pour créer une User Delegation Key puis un SAS Token 
- uploader des fichiers depuis [ce site](https://insideairbnb.com/get-the-data/) vers le datalake. 

Il est possible de **monitorer l'accès au secret** stocké dans le Keyvault. Pour cela il faut : 
- créer un **diagnostic setting** en sélectionnant les logs souhaités et la cible où seront stockés les logs (un log analytic workspace est créé auparavant si besoin) 

![diagnostic-setting](images/diagnostic-setting.png)

- les opérations peuvent ensuite être visualisées dans **Monitoring > Insights > Opérations** 
- on peut aussi retrouver les logs concernant les opérations sur le key vault avec la **query** : 
```sql
AzureDiagnostics
| where ResourceType  == "VAULTS"
```
- on peut retrouver dans la colonne **identity_claim_appid_g** le client ID du service principal qui s'est connecté au keyvault pour accéder au secret.
- d'après notre configuration, les logs sont également stockés dans notre **datalake** dans le container insights-logs-auditevent (normalement il est recommandé de ne pas stocker les logs dans le datalake que l'on cherche à protéger)

![container-logs](images/container-logs.png)

## Partie 3 : Configuration d'Azure Databricks 

Azure Databricks est une plateforme d'analyse de données basée sur **Apache Spark**, spécialement conçue pour le cloud Azure de Microsoft. Idéal pour le traitement de données volumineuses et pour le machine learning.

Fonctionnalités : 
- notebooks interactifs (python, R, scala, sql, java)
- ajout/suppression de ressources de calcul (compute) en fonction des besoins 
- machine learning (intégration avec Azure Machine Learning)
- workflows ETL avancés 
- sécurité avancée 

- Création de la ressource **databricks-mplatteau** depuis le portail Azure.

- Configuration du cluster en lançant le workspace et en accédant à l'onglet **compute**.

- Utilisation du service principal existant pour accéder au Datalake **dl-sas-read-mplatteau**. Il dispose du rôle **Storage Blob Data Contributor** et un secret est déjà créé et stocké dans le **Keyvault kv-mplatteau** : *sp-secret*. 

- Configuration du keyvault pour pouvoir interagir avec **Azure Databricks** (ajouter aussi notre adresse IP pour que le code python continue à fonctionner) : 

![kv-settings-adb](images/kv-settings-adb.png)

- Création d'un **secret scope** dans Azure Databricks en allant sur l'url : "https://\<databricks-instance>\#secrets/createScope"

![secret-scope](images/secret-scope.png)

- Création d'un **notebook python** dans Azure Databricks pour monter le **datalake** dans Azure Databricks. 

*Monter un Data Lake dans Azure Databricks signifie **établir une connexion entre un Data Lake (tel qu'Azure Data Lake Storage Gen1/Gen2 ou Azure Blob Storage) et un cluster Databricks**, afin que les données stockées dans le Data Lake puissent être utilisées directement depuis Databricks comme si elles faisaient partie du système de fichiers local. Cela permet d'accéder, d'explorer et de traiter ces données sans devoir les déplacer ou les copier.*

![notebook-adb](images/notebook-adb.png)

    - Client ID = ID du service principal qui permet de lire dans le datalake 
    - Secret = on utilise le secret scope créé dans Azure Databricks. Celui-ci se connecte au key vault et récupère le secret stocké (sp-secret = le password du service principal)
    - endpoint = tenant ID du service principal 
    - Source : \<container\>@\<storage account name\> , on peut ajouter à la fin de l'url le nom d'un dossier spécifique si besoin 
    - Mount point : le dossier dans Azure Databricks dans lequel on veut monter le datalake. 

![spark-read](images/spark-read.png)

## Partie 4 : Monitoring et alertes

### Activity logs 
 
**Activity logs** regroupe tous les logs concernant les ressources de la subscription. On peut ajouter des filtres sur le groupe de ressource pour voir uniquement nos ressources.

![activity-logs](images/activity-logs.png)

On peut exporter ces logs dans un **Log analytics workspace** en cliquant sur *Export Activity Logs* puis en créant un **diagnostic settings** (voir partie 2).

Dans le **Log Analytics Workspace**, on retrouve ces logs dans **Azure Activity** et on peut appliquer les mêmes filtres pour voir uniquement nos ressources : 
```sql 
AzureActivity
| where  ResourceGroup  == "RG_*********"
```

### Metrics 

Il existe plusieurs façons de suivre les métriques. Dans la ressource de notre datalake, on peut aller dans **Monitoring > Metrics** et visualiser la métrique souhaitée. On peut ensuite l'envoyer dans un **workbook** (*Send to workbook*) ou dans un **dasboard** (*pin to dashboard*). 

![adls-metric](images/adls-metric.png)

Pour créer un nouveau dashboard : Azure Portal > Dashboard (dans le menu latéral à gauche) > Create 

On peut envoyer des métriques depuis l'onglet **Metrics** des ressources, ou les créer directement depuis le dashboard en créant un widget de métriques et en choisissant le scope (la ressource concernée) et la métrique souhaitée. 

![adls-dashboard](images/adls-dashboard.png)

### Insights

Certaines métriques sont également automatiquement générées dans l'onglet **Monitoring > Insights**. On peut sélectionner des métriques de cette vue pour les ajouter à notre dashboard en sélectionnant **Pin to dashboard** sur une métrique, ou envoyer le raccourci vers cette vue en sélectionnant **Pin default workbook** en haut de la page. 

![adls-insights](images/adls-insights.png)

![metrics-vs-insights](images/metrics-vs-insights.png)

### Alerts

#### Configuration d'une alerte lorsque le Ingress dépasse 1 Go

Deux possibilités : 
    - depuis la métrique créée dans l'onglet Metrics ou depuis cette métrique sur le dashboard : **New alert rule**
    - depuis l'onglet Monitoring > Alerts : **Create**

![ingress-alert](images/ingress-alert.png)

On définir un **groupe d'action** pour lequel on va choisir le type d'action souhaité : SMS/Mail/Notification... On peut choisir :
- **Quick actions** : on donne un nom au groupe d'action et on entre immédiatement le mail (l'option SMS n'est pas disponible dans ce mode)
- **group action** : il y a plus d'options disponibles dont le mail et le sms 
    
![ingress-alert-group](images/ingress-alert-group.png)

On choisit un niveau de sévérité pour l'alerte.

![ingress-alert-level](images/ingress-alert-level.png)

#### Configuration regenerate key

On utilise le même outil et, au lieu de choisir une métrique et un seuil, on entre une requête KQL. Ici : 
```sql
 AzureActivity
| where OperationNameValue contains "regeneratekey"
| where ResourceGroup == "RG_*********"
```
Et on définit à partir de combien de lignes récupérées par la requête l'alerte est activée. Ici, on choisit 1 : dès qu'on a une regénération de clé, l'alerte est activée. 
Pour cette alerte, on crée un groupe d'action pour lequel un SMS est envoyé et on définit le niveau de sévérité à 1 : Error. 

Voici les alertes reçues : 
- dans l'onglet **Alerts** du storage account 

![alerts](images/alerts.png)

- par mail pour l'alerte sur **Ingress** 

![alert-mail](images/alert-mail.png)

- par SMS pour l'alerte sur la **Regenerate Key** :

![alert-sms](images/alert-sms.png)
