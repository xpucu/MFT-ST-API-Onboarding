"""
Axway SecureTransport Admin REST API Client.

Wraps the ST Admin REST API used to onboard accounts, create transfer sites,
applications, and subscriptions.

Authentication: raw API key value passed in the SECURETRANSPORT-API-KEY header.
No session cookie or CSRF token is required.

The base_url should include the full API path, e.g.:
  https://st-server.example.com:444/api/v2.0
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

logger = logging.getLogger(__name__)


class STApiClient:
    """Client for the Axway SecureTransport Admin REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl

        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "SECURETRANSPORT-API-KEY": api_key,
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(
        self, method: str, path: str, **kwargs
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute an HTTP request and return (success, result_dict).

        result_dict keys:
          - status_code (int)
          - data (dict | list | str)
          - url (str)
          - error (str) -- only when a connection-level exception occurs
        """
        url = self._url(path)
        try:
            response = self.session.request(
                method, url, verify=self.verify_ssl, timeout=30, **kwargs
            )
            try:
                data: Any = response.json()
            except Exception:
                data = response.text

            success = response.status_code in (200, 201, 202, 204)
            return success, {
                "status_code": response.status_code,
                "data": data,
                "url": url,
                "headers": dict(response.headers),
            }
        except requests.exceptions.SSLError as exc:
            return False, {
                "error": f"SSL error: {exc}. Disable SSL verification if using a self-signed certificate.",
                "url": url,
            }
        except requests.exceptions.ConnectionError as exc:
            return False, {
                "error": f"Connection error: {exc}",
                "url": url,
            }
        except requests.exceptions.Timeout:
            return False, {
                "error": "Request timed out after 30 seconds.",
                "url": url,
            }
        except requests.exceptions.RequestException as exc:
            return False, {"error": str(exc), "url": url}

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    def test_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """Verify connectivity and admin credentials. GET /accounts?limit=1."""
        return self._request("GET", "/accounts", params={"limit": 1})

    # ------------------------------------------------------------------
    # Accounts  -- POST /accounts
    # ------------------------------------------------------------------

    def create_account(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Create a new user account."""
        return self._request("POST", "/accounts", json=payload)

    def get_account(self, account_name: str) -> Tuple[bool, Dict[str, Any]]:
        """Retrieve an account by name."""
        return self._request("GET", f"/accounts/{account_name}")

    # ------------------------------------------------------------------
    # Transfer Sites  -- POST /sites
    # ------------------------------------------------------------------

    def create_site(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Create a transfer site (SSH, FTP, HTTP, AS2, PeSIT, etc.)."""
        return self._request("POST", "/sites", json=payload)

    def get_site(self, site_name: str) -> Tuple[bool, Dict[str, Any]]:
        """Retrieve a transfer site by name."""
        return self._request("GET", f"/sites/{site_name}")

    # ------------------------------------------------------------------
    # Applications  -- POST /applications
    # ------------------------------------------------------------------

    def create_application(
        self, payload: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Create a new application (typically type=Basic)."""
        return self._request("POST", "/applications", json=payload)

    def get_applications(
        self, app_type: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """List applications, optionally filtered by type."""
        params = {}
        if app_type:
            params["type"] = app_type
        return self._request("GET", "/applications", params=params)

    # ------------------------------------------------------------------
    # Subscriptions  -- POST /subscriptions
    # ------------------------------------------------------------------

    def create_subscription(
        self, payload: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Create a subscription linking account, folder, and application."""
        return self._request("POST", "/subscriptions", json=payload)

    # ------------------------------------------------------------------
    # Routes  -- POST /routes
    # ------------------------------------------------------------------

    def get_route_templates(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Return all Advanced Routing TEMPLATE routes.

        The response body follows the standard ST list envelope:
          { "result": [ {id, name, type, ...}, ... ], "resultSet": {count} }
        """
        return self._request("GET", "/routes", params={"type": "TEMPLATE"})

    def create_ssh_certificate(
        self,
        account_name: str,
        cert_name: str,
        private_key_pem: str,
        ca_password: str,
        validity_days: int = 3650,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Import a locally-generated RSA private key as an SSH private certificate
        for an account via POST /certificates (multipart/mixed).

        Uses urllib3 RequestField + encode_multipart_formdata to build the body,
        matching the approach in 3_Per_Account_Migration.py.

        Returns (success, result_dict).  result["data"]["id"] is the cert ID to
        reference from transfer sites as 'clientCertificate'.
        """
        import json as _json
        from requests.packages.urllib3.fields import RequestField
        from requests.packages.urllib3.filepost import encode_multipart_formdata

        json_data = {
            "name":           cert_name,
            "type":           "ssh",
            "usage":          "private",
            "account":        account_name,
            "subject":        f"CN={cert_name}",
            "overwrite":      "false",
            "validityPeriod": validity_days,
            "caPassword":     ca_password,
        }

        files = {
            "CertificateBody":    ("JSON_data.json", _json.dumps(json_data),  "application/json"),
            "CertificateContent": (f"{cert_name}.key", private_key_pem,       "application/octet-stream"),
        }

        fields = []
        for name, (filename, contents, mimetype) in files.items():
            rf = RequestField(name=name, data=contents, filename=filename)
            rf.make_multipart(content_disposition="attachment", content_type=mimetype)
            fields.append(rf)

        post_body, content_type = encode_multipart_formdata(fields)
        # Switch multipart/form-data → multipart/mixed (keeping the boundary parameter)
        content_type = "".join(("multipart/mixed",) + content_type.partition(";")[1:])

        url = self._url("/certificates")

        # Make a raw request with the custom Content-Type
        saved_ct = self.session.headers.get("Content-Type")
        self.session.headers["Content-Type"] = content_type
        try:
            response = self.session.post(url, data=post_body, verify=self.verify_ssl, timeout=60)
        finally:
            if saved_ct:
                self.session.headers["Content-Type"] = saved_ct
            else:
                self.session.headers.pop("Content-Type", None)

        try:
            data: Any = response.json()
        except Exception:
            data = response.text

        success = response.status_code in (200, 201)

        # Extract cert ID from body or Location header (mirrors reference code)
        cert_id = None
        if isinstance(data, dict):
            cert_id = data.get("id")
        if not cert_id and "Location" in response.headers:
            location = response.headers["Location"]
            if "/" in location:
                cert_id = location.split("/")[-1]
        if cert_id and isinstance(data, dict):
            data["id"] = cert_id

        return success, {
            "status_code": response.status_code,
            "data":        data,
            "url":         url,
            "headers":     dict(response.headers),
        }


    # ------------------------------------------------------------------
    # Payload builders
    # ------------------------------------------------------------------

    @staticmethod
    def build_account_payload(
        account_name: str,
        password: str,
        uid: int,
        gid: int,
        home_folder: str,
        email: Optional[str] = None,
        notes: Optional[str] = None,
        custom_properties: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Build the JSON payload for POST /accounts (type=user).

        Fields follow the account_onboarding workflow from the ST API guide.

        Notes from swagger/admin/account.yaml:
          - uid and gid are string fields (despite holding numeric values)
          - notes is a top-level string field (maxLength 2048)
          - additionalAttributes keys must be 10-255 characters and match [a-zA-Z0-9_.]+
          - contact.email holds the account contact email
        """
        payload: Dict[str, Any] = {
            "name": account_name,
            "type": "user",
            "uid":  str(uid),   # schema type: string
            "gid":  str(gid),   # schema type: string
            "homeFolder": home_folder,
            "user": {
                "name": account_name,
                "passwordCredentials": {"password": password},
            },
        }
        if email:
            payload["contact"] = {"email": email}
        if notes:
            payload["notes"] = notes
        if custom_properties:
            payload["additionalAttributes"] = custom_properties
        return payload

    @staticmethod
    def build_application_payload(app_name: str) -> Dict[str, Any]:
        """Build the JSON payload for POST /applications (type=Basic)."""
        return {"name": app_name, "type": "Basic"}

    @staticmethod
    def build_subscription_payload(
        account_name: str,
        folder: str,
        application_name: str,
        transfer_configs: Optional[list] = None,
        file_retention_period: Optional[int] = None,
        schedules: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Build the JSON payload for POST /subscriptions (type=Basic).

        transfer_configs example:
          [
            {"tag": "PARTNER-IN",  "outbound": False, "site": "site-name"},
            {"tag": "PARTNER-OUT", "outbound": True,  "site": "site-name"},
          ]
        Omit `site` key for CIT inbound (partner connects to ST; no site needed).

        file_retention_period: number of days to retain files (1 = 1 day).
        schedules: list of schedule objects (e.g. HOURLY/PERMINUTES for SIT pull).
        """
        payload: Dict[str, Any] = {
            "type":        "Basic",
            "folder":      folder,
            "account":     account_name,
            "application": application_name,
        }
        if transfer_configs:
            payload["transferConfigurations"] = transfer_configs
        if file_retention_period is not None:
            payload["fileRetentionPeriod"] = file_retention_period
        if schedules:
            payload["schedules"] = schedules
        return payload

    @staticmethod
    def build_ar_subscription_payload(
        account_name: str,
        folder: str,
        application_name: str,
        file_retention_period: Optional[int] = None,
        schedules: Optional[list] = None,
        transfer_configurations: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Build the JSON payload for POST /subscriptions (type=AdvancedRouting).

        Used for both INBOUND_CIT and SIT_PULL Advanced Routing flows.
        Optional schedules (e.g. HOURLY/PERMINUTES), fileRetentionPeriod, and
        transferConfigurations are included when provided.
        ST requires transferConfigurations to contain the pull site name whenever
        fileRetentionPeriod is set.
        """
        payload: Dict[str, Any] = {
            "type":        "AdvancedRouting",
            "folder":      folder,
            "account":     account_name,
            "application": application_name,
        }
        if file_retention_period is not None:
            payload["fileRetentionPeriod"] = file_retention_period
        if schedules:
            payload["schedules"] = schedules
        if transfer_configurations:
            payload["transferConfigurations"] = transfer_configurations
        return payload

    @staticmethod
    def build_composite_route_payload(
        route_name: str,
        account_name: str,
        route_template_id: str,
        subscription_id: str,
    ) -> Dict[str, Any]:
        """
        Build the JSON payload for POST /routes (type=COMPOSITE).

        The COMPOSITE route binds the existing TEMPLATE to the account via
        the AdvancedRouting subscription.  The template already contains the
        SIMPLE route with routing steps (PublishToAccount, email notification),
        so no separate SIMPLE route needs to be created — it is inherited from
        the template at runtime.

        subscription_id may be a '${var}' placeholder resolved at execution time.
        """
        return {
            "name":          route_name,
            "type":          "COMPOSITE",
            "conditionType": "MATCH_ALL",
            "account":       account_name,
            "routeTemplate": route_template_id,
            "subscriptions": [subscription_id],
            "steps":         [],
        }

    @staticmethod
    def build_ssh_site_payload(
        site_name: str,
        account_name: str,
        host: str,
        port: str,
        remote_username: str,
        remote_password: Optional[str] = None,
        ssh_key_alias: Optional[str] = None,
        upload_folder: str = "/",
        download_folder: str = "/",
        download_pattern: str = "*",
        verify_fingerprint: bool = False,
        fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the JSON payload for POST /sites (type=ssh / SFTP)."""
        payload: Dict[str, Any] = {
            "name":             site_name,
            "type":             "ssh",
            "protocol":         "ssh",
            "dmz":              "none",
            "host":             host,
            "port": str(port),
            "userName": remote_username,
            "account": account_name,
            "uploadFolder": upload_folder,
            "downloadFolder": download_folder,
            "downloadPattern": download_pattern,
            "verifyFinger": verify_fingerprint,
        }
        if remote_password:
            payload["usePassword"] = True
            payload["password"] = remote_password
        elif ssh_key_alias:
            payload["usePassword"] = False
            payload["clientCertificate"] = ssh_key_alias
        if verify_fingerprint and fingerprint:
            payload["fingerPrint"] = fingerprint
        return payload

    @staticmethod
    def build_ftp_site_payload(
        site_name: str,
        account_name: str,
        host: str,
        port: str,
        remote_username: str,
        remote_password: str,
        upload_folder: str = "/",
        download_folder: str = "/",
        download_pattern: str = "*",
        active_mode: bool = False,
        is_secure: bool = False,
        verify_cert: bool = False,
    ) -> Dict[str, Any]:
        """Build the JSON payload for POST /sites (type=ftp / FTP or FTPS)."""
        return {
            "name":             site_name,
            "type":             "ftp",
            "protocol":         "ftp",
            "dmz":              "none",
            "host":             host,
            "port": str(port),
            "userName": remote_username,
            "usePassword": True,
            "password": remote_password,
            "account": account_name,
            "uploadFolder": upload_folder,
            "downloadFolder": download_folder,
            "downloadPattern": download_pattern,
            "activeMode": active_mode,
            "isSecure": is_secure,
            "verifyCert": verify_cert,
        }

    @staticmethod
    def build_http_site_payload(
        site_name: str,
        account_name: str,
        host: str,
        port: str,
        remote_username: str,
        remote_password: str,
        is_secure: bool = True,
        verify_cert: bool = True,
        request_mode: str = "POST",
        upload_folder: str = "/",
        download_folder: str = "/",
        download_pattern: str = "*",
    ) -> Dict[str, Any]:
        """Build the JSON payload for POST /sites (type=http / HTTP or HTTPS)."""
        return {
            "name":             site_name,
            "type":             "http",
            "protocol":         "http",
            "dmz":              "none",
            "host":             host,
            "port": str(port),
            "isSecure": is_secure,
            "verifyCert": verify_cert,
            "userName": remote_username,
            "usePassword": True,
            "password": remote_password,
            "account": account_name,
            "requestMode": request_mode,
            "uploadFolder": upload_folder,
            "downloadFolder": download_folder,
            "downloadPattern": download_pattern,
        }

