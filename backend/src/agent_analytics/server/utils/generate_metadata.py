# generate_metadata.py
from onelogin.saml2.settings import OneLogin_Saml2_Settings
import os
from dotenv import load_dotenv

load_dotenv()

def generate_metadata():
    # Basic SAML settings
    settings = {
        "strict": True,
        "debug": True,
        "sp": {
            "entityId": os.getenv('SAML_SP_ENTITY_ID'),
            "assertionConsumerService": {
                "url": os.getenv('SAML_SP_ACS_URL'),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            },
            "singleLogoutService": {
                "url": os.getenv('SAML_SP_SLO_URL'),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": ""
        },
        "security": {
            "nameIdEncrypted": False,
            "authnRequestsSigned": False,
            "logoutRequestSigned": False,
            "logoutResponseSigned": False,
            "signMetadata": False,
            "wantMessagesSigned": False,
            "wantAssertionsSigned": False,
            "wantNameIdEncrypted": False,
            "requestedAuthnContext": True
        }
    }

    saml_settings = OneLogin_Saml2_Settings(settings=settings, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    
    # Save metadata to file
    with open("sp_metadata.xml", "w") as f:
        f.write(metadata)
    
    print("Metadata has been saved to sp_metadata.xml")
    print("\nMetadata content:")
    print(metadata)

if __name__ == "__main__":
    generate_metadata()