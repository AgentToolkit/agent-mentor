import os
import traceback
from datetime import UTC, datetime, timedelta
from urllib import parse

import jwt
from fastapi import (
    Depends,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jwt import InvalidTokenError

from agent_analytics.server.db.operations import LoginTracker
from agent_analytics.server.logger import logger
from agent_analytics.server.saml_auth import SAMLAuth, SAMLUser

DEPLOYMENT_PLATFORM = os.environ.get("WXO_DEPLOYMENT_PLATFORM", "")
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "false").lower() == "true"
API_KEY_AUTH_ENABLED = os.getenv("API_KEY_AUTH_ENABLED", "false").lower() == "true"
INBOUND_API_KEY = os.getenv("INBOUND_API_KEY", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 20160  #14 days - Will be overridden by SAML session lifetime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
saml_auth = SAMLAuth()

def should_bypass_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> bool:
    """Check if authentication should be bypassed entirely"""
    if API_KEY_AUTH_ENABLED and x_api_key and INBOUND_API_KEY == x_api_key:
        return True
    else:
        return BYPASS_AUTH
            # or \
            # (DEPLOYMENT_PLATFORM.lower() == 'saas' or DEPLOYMENT_PLATFORM.lower() == 'local' or DEPLOYMENT_PLATFORM.lower() == 'laptop-lite')

def validate_admin_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> bool:
    """Validate admin API key for admin routes.

    Even if BYPASS_AUTH is enabled, admin routes still require the admin API key.
    Returns True if valid, raises HTTPException if invalid.
    """
    if not ADMIN_API_KEY:
        logger.warning("ADMIN_API_KEY not configured - admin routes are disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key not configured"
        )

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key required",
            headers={"WWW-Authenticate": "API-Key"}
        )

    if x_api_key != ADMIN_API_KEY:
        logger.warning(f"Invalid admin API key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key"
        )

    return True

def create_bypass_user() -> SAMLUser:
    """Create a default user for bypass mode"""
    return SAMLUser(
        username="bypass_user",
        email="bypass@system.local",
        full_name="Bypass User",
        saml_session_index=None,
        saml_name_id=None
    )

def create_access_token(data: dict, auth_instance=None):
    to_encode = data.copy()
    session_lifetime = int(os.getenv('SAML_SESSION_LIFETIME_MINUTES', ACCESS_TOKEN_EXPIRE_MINUTES))
    expire = datetime.now(UTC) + timedelta(minutes=session_lifetime)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(request: Request):
    """Get current user with bypass support"""
    x_api_key = request.headers.get("X-API-Key")
    # Check if auth bypass is enabled
    if should_bypass_auth(x_api_key):
        logger.debug("Authentication bypass enabled - returning bypass user")
        return create_bypass_user()

    logger.debug("Starting user authentication")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = request.cookies.get("auth_token")

    if not token:
        authorization = request.headers.get("Authorization")
        if not authorization:
            logger.debug("No authentication token found in cookie or header")
            raise credentials_exception

        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            logger.debug(f"Invalid authentication scheme: {scheme}")
            raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            logger.debug("No username found in token payload")
            raise credentials_exception

        user = SAMLUser(
            username=username,
            email=payload.get("email"),
            full_name=payload.get("name"),
            saml_session_index=payload.get("saml_session_index"),
            saml_name_id=payload.get("saml_name_id")
        )
        return user
    except InvalidTokenError as e:
        logger.debug(f"JWT decode error: {str(e)}")
        raise credentials_exception from e

def is_embedded(request: Request) -> bool:
    return request.query_params.get('embed', '') == 'true'

def is_pass_through(request: Request) -> bool:
    return is_embedded(request) or saml_auth.config._is_testing(request) or should_bypass_auth()

# Authentication Routes
async def auth_login_get(request: Request):
    """GET handler for universal login - redirects to SAML login for non-localhost"""
    if should_bypass_auth():
        return RedirectResponse(url="/")

    if not is_pass_through(request):
        return RedirectResponse(url="/saml/login")
    return RedirectResponse(url="/")

async def auth_login_post(request: Request, username: str = Form(...)):
    """POST handler for universal login - handles local auth"""
    if should_bypass_auth():
        return RedirectResponse(url="/")

    if not is_pass_through(request):
        return RedirectResponse(url="/saml/login")

    username = username if username and username != "" else "embed"

    access_token = create_access_token(
        data={
            "sub": username,
            "email": f"{username}@local",
            "name": f"Local Dev ({username})",
        }
    )

    response = RedirectResponse(
        url="/" if not is_embedded(request) else "/?embed=true",
        status_code=status.HTTP_302_FOUND
    )

    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(os.getenv('SAML_SESSION_LIFETIME_MINUTES', ACCESS_TOKEN_EXPIRE_MINUTES)) * 60
    )

    await LoginTracker.log_login(
        username=username,
        email=username+"@localhost",
        full_name="Local Dev",
        ip_address=request.client.host
    )
    return response

  # Add new auto-login endpoint
async def auth_auto_login(request: Request):
    """Auto login handler for embedded mode"""
    if should_bypass_auth():
        return Response(status_code=status.HTTP_200_OK)

    if not is_embedded(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auto-login only available in embedded mode"
        )

    # Create token for embedded user
    access_token = create_access_token(
        data={
            "sub": "embed",
            "email": "embed@embedded",
            "name": "Embedded User",
        }
    )

    response = Response(status_code=status.HTTP_200_OK)
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=int(os.getenv('SAML_SESSION_LIFETIME_MINUTES', ACCESS_TOKEN_EXPIRE_MINUTES)) * 60
    )

    await LoginTracker.log_login(
        username="embed",
        email="embed@embedded",
        full_name="Embedded User",
        ip_address=request.client.host
    )

    return response

async def auth_logout(request: Request):
    """Universal logout that handles both SAML and local auth"""
    if should_bypass_auth():
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    response = RedirectResponse(
        url="/",
        status_code=status.HTTP_302_FOUND,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

    is_local = is_pass_through(request)
    response.delete_cookie(
        key="auth_token",
        path="/",
        secure=not is_local,
        httponly=True,
        samesite="lax" if is_local else "strict"
    )

    if not is_local:
        try:
            req = await saml_auth.prepare_fastapi_request(request)
            auth = saml_auth.init_saml_auth(req)
            saml_logout_url = auth.logout()

            saml_response = RedirectResponse(
                url=saml_logout_url,
                status_code=status.HTTP_302_FOUND,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
            saml_response.delete_cookie(
                key="auth_token",
                path="/",
                secure=True,
                httponly=True,
                samesite="strict"
            )
            return saml_response

        except Exception as e:
            logger.error(f"SAML logout failed: {str(e)}, falling back to basic logout")

    return response

# SAML Routes
async def saml_login(request: Request):
    if should_bypass_auth():
        return RedirectResponse(url="/")

    try:
        req = await saml_auth.prepare_fastapi_request(request)
        auth = saml_auth.init_saml_auth(req)
        return RedirectResponse(auth.login())
    except Exception as e:
        logger.error(f"Error in SAML login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e

async def saml_logout(request: Request):
    if should_bypass_auth():
        return RedirectResponse(url="/")

    try:
        req = await saml_auth.prepare_fastapi_request(request)
        auth = saml_auth.init_saml_auth(req)

        response = RedirectResponse(
            url=auth.logout(),
            status_code=status.HTTP_302_FOUND
        )

        response.delete_cookie(
            key="auth_token",
            secure=True,
            httponly=True,
            samesite="strict"
        )

        return response

    except Exception as e:
        logger.error(f"Error in SAML logout: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e

async def refresh_metadata(current_user: SAMLUser = Depends(get_current_user)):
    if should_bypass_auth():
        return {"message": "SAML metadata refresh not available in bypass mode"}

    try:
        saml_auth.config.refresh_metadata()
        return {"message": "SAML metadata refreshed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh metadata: {str(e)}"
        ) from e

async def saml_acs(request: Request):
    if should_bypass_auth():
        return RedirectResponse(url="/")

    try:
        req = await saml_auth.prepare_fastapi_request(request)
        auth = saml_auth.init_saml_auth(req)

        logger.info("Processing SAML Response...")
        auth.process_response()

        # Log the full SAML response for debugging
        logger.debug("========== Full SAML Response ==========")
        logger.debug(f"NameId: {auth.get_nameid()}")
        logger.debug(f"Session Index: {auth.get_session_index()}")
        logger.debug(f"Session Expiration: {auth.get_session_expiration()}")
        logger.debug("=======================================")

        errors = auth.get_errors()

        if errors:
            logger.error(f"SAML Authentication errors: {errors}")
            logger.error(f"Error reason: {auth.get_last_error_reason()}")
            error_message = f"SAML Authentication failed: {', '.join(errors)}"
            return RedirectResponse(
                url=f"/?error={parse.quote(error_message)}",
                status_code=status.HTTP_302_FOUND
            )

        if not auth.is_authenticated():
            return RedirectResponse(
                url="/?error=Authentication failed",
                status_code=status.HTTP_302_FOUND
            )

        saml_attributes = auth.get_attributes()

        # Detailed logging of SAML attributes
        logger.debug("========== SAML Response Debug Info ==========")
        logger.debug(f"All SAML attributes received: {saml_attributes}")
        logger.debug("Individual SAML attributes:")
        for attr_name, attr_values in saml_attributes.items():
            logger.debug(f"Attribute: {attr_name}")
            logger.debug(f"Values: {attr_values}")
            logger.debug(f"Type: {type(attr_values)}")
        logger.debug("=============================================")

        # Extract user groups from SAML attributes
        # The actual attribute name might be different depending on your IdP
        # Common names are: groups, memberOf, group, roles
        user_groups = saml_attributes.get('blueGroups', [])

        # Define allowed groups (you might want to move this to config)
        allowed_group = os.getenv('ALLOWED_GROUP', 'cn=agent-analytics-users,ou=memberlist,ou=ibmgroups,o=ibm.com')
        admin_group = os.getenv('ADMIN_GROUP', 'cn=agent-analytics-admins,ou=memberlist,ou=ibmgroups,o=ibm.com')

        # Check if user belongs to any allowed group
        has_access = allowed_group in user_groups

        if not has_access:
            logger.warning(f"User with groups {user_groups} denied access")
            error_message = "You do not yet have permission to access this application. If you already completed the below survey, allow up to 48 hours for your user to be created."
            return RedirectResponse(
                url=f"/?error={parse.quote(error_message)}",
                status_code=status.HTTP_302_FOUND
            )

        # Check if user is admin
        is_admin = admin_group in user_groups

        username = saml_attributes.get('uid', [None])[0] or saml_attributes.get('emailAddress', [None])[0]
        if not username:
            return RedirectResponse(
                url=f"/?error={parse.quote('Missing username or email in SAML attributes')}",
                status_code=status.HTTP_302_FOUND
            )

        email = saml_attributes.get('emailAddress', [None])[0]
        name = saml_attributes.get('cn', [None])[0]

        await LoginTracker.log_login(
            username=username,
            email=email,
            full_name=name,
            ip_address=request.client.host
        )

        access_token = create_access_token(
            data={
                "sub": username,
                "email": email,
                "name": name,
                "saml_session_index": auth.get_session_index(),
                "saml_name_id": auth.get_nameid(),
                "is_admin": is_admin
            },
            auth_instance=auth
        )

        response = RedirectResponse(
            url="/",
            status_code=status.HTTP_302_FOUND
        )

        response.set_cookie(
            key="auth_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=int(os.getenv('SAML_SESSION_LIFETIME_MINUTES', ACCESS_TOKEN_EXPIRE_MINUTES)) * 60
        )

        return response

    except Exception as e:
        logger.error(f"Error in SAML ACS: {str(e)}")
        error_message = "An error occurred during authentication. Please try again or contact support."
        return RedirectResponse(
            url=f"/?error={parse.quote(error_message)}",
            status_code=status.HTTP_302_FOUND
        )
