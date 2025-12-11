import os
from pathlib import Path


class Config:
    FLAVOR = os.getenv('FLAVOR', 'prod').lower()
    PROJECT_ROOT = os.getenv('PROJECT_ROOT', '/app')

    # Base configuration
    BASE_DOMAINS = {
        'pre_prod': 'https://dashboard-agent-analytics.agent-analytics-9ca4d14d48413d18ce61b80811ba4308-0000.us-south.containers.appdomain.cloud',
        'prod': 'https://dashboard-agent-analytics.agent-analytics-9ca4d14d48413d18ce61b80811ba4308-0000.us-south.containers.appdomain.cloud',
        'dev': 'https://dashboard-dev-agent-analytics.agent-analytics-9ca4d14d48413d18ce61b80811ba4308-0000.us-south.containers.appdomain.cloud'
    }

    METADATA_FILES = {
        'pre_prod': '/app/config/saml-metadata/federation_metadata.xml',
        'prod': '/app/config/saml-metadata/federation_metadata.xml',
        'dev': '/app/config/saml-metadata/federation_metadata.xml'
    }

    # Fallback to baked-in files for backward compatibility (remove after migration)
    FALLBACK_METADATA_FILES = {
        'pre_prod': '/src/server/metadata/federation_metadata_pre_prod.xml',
        'prod': '/src/server/metadata/federation_metadata_prod.xml',
        'dev': '/src/server/metadata/federation_metadata_dev.xml'
    }

    @property
    def SERVICE_DOMAIN(self):
        return os.getenv('SERVICE_DOMAIN', self.BASE_DOMAINS.get(self.FLAVOR))

    @property
    def SAML_METADATA_FILE(self):
        # Try mounted ConfigMap first
        mounted_path = self.METADATA_FILES.get(self.FLAVOR)
        if mounted_path and Path(mounted_path).exists():
            return mounted_path

        # Fallback to baked-in file (for backward compatibility)
        fallback_path = str(Path(self.PROJECT_ROOT) / self.FALLBACK_METADATA_FILES.get(self.FLAVOR).lstrip('/'))
        if Path(fallback_path).exists():
            return fallback_path

        # Override from environment variable
        return os.getenv('SAML_METADATA_FILE', mounted_path)

    @property
    def SAML_SP_ENTITY_ID(self):
        return f"{self.SERVICE_DOMAIN}/saml/metadata"

    @property
    def SAML_SP_ACS_URL(self):
        return f"{self.SERVICE_DOMAIN}/saml/acs"

    @property
    def SAML_SP_SLO_URL(self):
        return f"{self.SERVICE_DOMAIN}/saml/logout"

config = Config()
