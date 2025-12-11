import asyncio
import os
import xml.etree.ElementTree as ET
from functools import lru_cache

import requests
from fastapi import Request
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from pydantic import BaseModel

from agent_analytics.server.config import config
from agent_analytics.server.logger import logger


class SAMLMetadataParser:
    NAMESPACES = {
        'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
        'ds': 'http://www.w3.org/2000/09/xmldsig#'
    }

    def __init__(self, metadata_url: str = None, metadata_file: str = None):
        self.metadata_url = metadata_url
        self.metadata_file = metadata_file or config.SAML_METADATA_FILE

    async def fetch_metadata(self) -> dict:
        """Fetch and parse SAML metadata from URL or file"""
        if self.metadata_url:
            response = requests.get(self.metadata_url)
            metadata_content = response.text
        elif self.metadata_file:
            with open(self.metadata_file) as f:
                metadata_content = f.read()
        else:
            raise ValueError("Either metadata_url or metadata_file must be provided")

        return self._parse_metadata(metadata_content)

    def _parse_metadata(self, metadata_content: str) -> dict:
        root = ET.fromstring(metadata_content)

        idp_descriptor = root.find('.//md:IDPSSODescriptor', self.NAMESPACES)
        if idp_descriptor is None:
            raise ValueError("No IdP descriptor found in metadata")

        cert_node = idp_descriptor.find('.//ds:X509Certificate', self.NAMESPACES)
        sso_node = idp_descriptor.find(
            './/md:SingleSignOnService[@Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"]',
            self.NAMESPACES
        )
        slo_node = idp_descriptor.find(
            './/md:SingleLogoutService[@Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"]',
            self.NAMESPACES
        )
        entity_descriptor = root.find('.', self.NAMESPACES)

        return {
            'entity_id': entity_descriptor.get('entityID') if entity_descriptor is not None else None,
            'sso_url': sso_node.get('Location') if sso_node is not None else None,
            'slo_url': slo_node.get('Location') if slo_node is not None else None,
            'certificate': cert_node.text.strip() if cert_node is not None else None
        }

class SAMLConfig:
    def __init__(self):
        if not self._is_testing():
            self.metadata_parser = SAMLMetadataParser(
                metadata_file=config.SAML_METADATA_FILE
            )
            self.settings = self._initialize_settings()

    @classmethod
    def _is_testing(self, req=None):
        return os.getenv("TEST", "false").lower() in ('true', '1', 'yes', 'on')

    def _read_file(self, file_path):
        with open(file_path) as f:
            return f.read().strip()

    @lru_cache
    def _initialize_settings(self) -> dict:
        metadata = asyncio.run(self.metadata_parser.fetch_metadata())
        session_lifetime = int(os.getenv('SAML_SESSION_LIFETIME_MINUTES', 60))

        # Read SP certificate and private key
        sp_private_key = ""
        sp_certificate = ""
        if os.getenv('SAML_SP_PRIVATE_KEY_FILE'):
            sp_private_key = self._read_file(os.getenv('SAML_SP_PRIVATE_KEY_FILE'))
        if os.getenv('SAML_SP_CERTIFICATE_FILE'):
            sp_certificate = self._read_file(os.getenv('SAML_SP_CERTIFICATE_FILE'))

        return {
            "strict": True,
            "debug": True,
            "sp": {
                "entityId": config.SAML_SP_ENTITY_ID,
                "assertionConsumerService": {
                    "url": config.SAML_SP_ACS_URL,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                },
                "singleLogoutService": {
                    "url": config.SAML_SP_SLO_URL,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "x509cert": sp_certificate,
                "privateKey": sp_private_key
            },
            "idp": {
                "entityId": metadata['entity_id'],
                "singleSignOnService": {
                    "url": metadata['sso_url'],
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "singleLogoutService": {
                    "url": metadata['slo_url'],
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "x509cert": metadata['certificate']
            },
            "security": {
                "nameIdEncrypted": False,
                "authnRequestsSigned": True,
                "logoutRequestSigned": True,
                "logoutResponseSigned": True,
                "signMetadata": True,
                "wantMessagesSigned": True,
                "wantAssertionsSigned": True,
                "wantNameIdEncrypted": False,
                "requestedAuthnContext": True,
                "sessionLifetime": session_lifetime
            }
        }

    def get_settings(self):
        """Safely get SAML settings"""
        if self.settings is None:
            return {}  # Return empty settings for localhost
        return self.settings

    def refresh_metadata(self):
        """Force refresh of cached metadata"""
        self._initialize_settings.cache_clear()
        self.settings = self._initialize_settings()

class SAMLAuth:
    def __init__(self):
        self.config = SAMLConfig()

    async def prepare_fastapi_request(self, request: Request) -> dict:
        """Prepare FastAPI request for python3-saml"""
        # Get the form data
        form_data = {}
        if request.method == "POST":
            try:
                form_data = await request.form()
                form_data = dict(form_data)
            except Exception as e:
                logger.error(f"Error getting form data: {e}")
                form_data = {}

        # Get the host from headers or URL
        host = request.headers.get('host') or request.url.netloc

        # Build the request data dictionary
        request_data = {
            'https': 'on',
            'http_host': host,
            'script_name': request.url.path,
            'server_port': 443,
            'get_data': dict(request.query_params),
            'post_data': form_data
        }

        # request_data = {
        #     'https': 'on' if request.url.scheme == 'https' else 'off',
        #     'http_host': host,
        #     'script_name': request.url.path,
        #     'server_port': request.url.port or (443 if request.url.scheme == 'https' else 80),
        #     'get_data': dict(request.query_params),
        #     'post_data': form_data
        # }


        # Add X-Forwarded headers if they exist
        for header in ['X-Forwarded-For', 'X-Forwarded-Proto', 'X-Forwarded-Host']:
            if header in request.headers:
                request_data[header.lower().replace('-', '_')] = request.headers[header]

        return request_data

    def init_saml_auth(self, req):
        """Initialize SAML auth only if not on localhost"""
        if self.config._is_testing(req):
            return None
        if self.config.settings is None:
            raise ValueError("SAML settings not properly initialized")
        return OneLogin_Saml2_Auth(req, self.config.settings)

class SAMLUser(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    saml_attributes: dict | None = None
    saml_session_index: str | None = None
    saml_name_id: str | None = None
    groups: list | None = []  # Add this line

