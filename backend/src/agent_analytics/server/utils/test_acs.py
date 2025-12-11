# test_acs.py
from saml_auth import SAMLAuth
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

auth = SAMLAuth()
settings = auth.config.settings

print("Configured ACS URL:", settings["sp"]["assertionConsumerService"]["url"])
print("Configured Entity ID:", settings["sp"]["entityId"])