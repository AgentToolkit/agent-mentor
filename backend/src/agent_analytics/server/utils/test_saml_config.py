# test_saml_config.py
from agent_analytics.server.saml_auth import SAMLAuth
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

def test_saml_configuration():
    auth = SAMLAuth()
    
    # Test metadata parsing
    print("\nTesting IdP Settings:")
    print("Entity ID:", auth.config.settings['idp']['entityId'])
    print("SSO URL:", auth.config.settings['idp']['singleSignOnService']['url'])
    print("SLO URL:", auth.config.settings['idp']['singleLogoutService']['url'])
    print("Certificate present:", bool(auth.config.settings['idp']['x509cert']))
    
    # Test SP settings
    print("\nTesting SP Settings:")
    print("Entity ID:", auth.config.settings['sp']['entityId'])
    print("ACS URL:", auth.config.settings['sp']['assertionConsumerService']['url'])
    print("SLO URL:", auth.config.settings['sp']['singleLogoutService']['url'])
    
    # Generate test auth request
    auth_instance = auth.init_saml_auth({
        'http_host': 'localhost',
        'script_name': '',
        'get_data': {},
        'post_data': {},
        'https': 'on'
    })
    
    login_url = auth_instance.login()
    print("\nTest login URL:", login_url)

if __name__ == "__main__":
    test_saml_configuration()