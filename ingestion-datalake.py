from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

load_dotenv()

### Récupération du secret du SP Principal dans le key vault ###

# Configuration keyvault
key_vault_url = os.getenv("KEYVAULT_URL")
secret_name = os.getenv("SECRET_NAME")

# Informations du SP Secondaire pour se connecter au key vault
tenant_id_secondary = os.getenv("TENANT_ID")
client_id_secondary = os.getenv("SP_ID_SECONDARY")
client_secret_secondary = os.getenv("SP_SECONDARY_PASSWORD")


# Authentification avec DefaultAzureCredential
credential = ClientSecretCredential(tenant_id_secondary, client_id_secondary, client_secret_secondary)
client = SecretClient(vault_url=key_vault_url, credential=credential)

# Récupération du secret
retrieved_secret = client.get_secret(secret_name)
print(f"Secret Value: {retrieved_secret.value}")

### Utilisation du SP Principal pour créer une User delegation key ### 

# Informations du SP Principal
tenant_id_principal = os.getenv("TENANT_ID")
client_id_principal = os.getenv("SP_ID_PRINCIPAL")
client_secret_principal = retrieved_secret.value

# Nom du compte de stockage
storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME")

# Authentification avec le SP Principal
credential = ClientSecretCredential(tenant_id_principal, client_id_principal, client_secret_principal)

# Connexion au Blob Service Client
blob_service_client = BlobServiceClient(
    account_url=f"https://{storage_account_name}.blob.core.windows.net/",
    credential=credential
)

# Générer la User Delegation Key
user_delegation_key = blob_service_client.get_user_delegation_key(
    datetime.now(timezone.utc) , datetime.now(timezone.utc) + timedelta(hours=1)
)


print("User Delegation Key :")
print(user_delegation_key.value)

### Génération SAS token à partir de la user delegation key ### 

current_time = datetime.now(timezone.utc)
key_start_time_str = current_time.strftime('%Y-%m-%dT%H:%M:%SZ')
key_expiry_time_str = (current_time + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ') 

sas = generate_container_sas(
        account_name=storage_account_name,
        container_name="datastorage",
        user_delegation_key=user_delegation_key,
        permission=ContainerSasPermissions(read=True),
        expiry=key_expiry_time_str,
        start=key_start_time_str
    )

print(f"SAS : {sas}")

### Utilisation du SAS token pour upload un fichier csv dans le datalake ### 


# URL principale d'Inside Airbnb
base_url = "http://insideairbnb.com/get-the-data.html"

# Dossier pour enregistrer les fichiers
download_dir = "inside_airbnb_data"
os.makedirs(download_dir, exist_ok=True)

# Faire une requête à la page principale
response = requests.get(base_url)
if response.status_code != 200:
    print(f"Impossible de charger la page principale : {response.status_code}")
    exit()

# Analyser le contenu HTML
soup = BeautifulSoup(response.text, "html.parser")

# Trouver tous les liens contenant des données pour l'Espagne
links = soup.find_all("a", href=True)
spain_links = [link["href"] for link in links if "spain" in link["href"]]


# Télécharger et uploader chaque fichier directement
for url in spain_links:
    # Extraire le chemin cible depuis l'URL (exemple : catalonia/barcelona/reviews.csv)
    filename = url.split("/")[-1]
    region_city = "/".join(url.split("/")[-5:-3])  # Exemple : catalonia/barcelona
    local_path = os.path.join(f"{region_city.replace('/', '_')}_{filename}")
    blob_path = f"airbnb/spain/{local_path}"

    # Création du Blob Client
    blob_client = blob_service_client.get_blob_client(container="datastorage", blob=blob_path)

    # Télécharger le fichier depuis l'URL
    print(f"Téléchargement et upload de {url} vers {blob_path}...")
    response = requests.get(url, stream=True)

    # Vérifier que la requête est réussie
    if response.status_code == 200:
        # Upload directement au Data Lake
        blob_client.upload_blob(response.raw, overwrite=True)
        print(f"Fichier {blob_path} uploadé avec succès.")
    else:
        print(f"Erreur lors du téléchargement de {url}: {response.status_code}")

print("Tous les fichiers ont été uploadés directement dans le Data Lake.")