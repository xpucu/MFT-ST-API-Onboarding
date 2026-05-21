"""
Account Onboarding page.

Supported flow patterns
-----------------------
INBOUND_CIT   Partner connects to ST and uploads files; ST routes to internal
              recipient via Advanced Routing (COMPOSITE + template).
SIT_PULL      ST pulls files from a remote partner system and uploads them
              to an internal SharePoint document library.
"""

import io
import json
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

import paramiko
import streamlit as st

from branding import (
    apply_branding,
    ax_success, ax_warning, ax_error, ax_info, ax_button,
    icon_img,
    ICO_SUCCESS, ICO_ERROR, ICO_WARNING, ICO_ROCKET, ICO_STOP, ICO_SEARCH,
    ICO_PAPERCLIP, ICO_REFRESH, ICO_ADMIN, ICO_PIN,
)
from st_api_client import STApiClient

st.set_page_config(
    page_title="Account Onboarding - ST Onboarding",
    page_icon=None,
    layout="wide",
)
apply_branding()

st.title("Account Onboarding")
st.markdown(
    "Fill in the form below to onboard a new account on SecureTransport. "
    "Required fields are marked with *."
)

# ------------------------------------------------------------------
# Guard: require admin config first
# ------------------------------------------------------------------
cfg: dict = st.session_state.get("st_config", {})
if not cfg.get("configured"):
    ax_warning(
        "SecureTransport is not configured. "
        "Go to <strong>Admin Configuration</strong> and save a valid connection first."
    )
    st.stop()

ax_success(f"Connected to <strong>{cfg['base_url']}</strong>.")
st.divider()


def _st_cfg() -> dict:
    """Always return the live st_config dict from session state."""
    return st.session_state.get("st_config", {})


def _fetch_ar_template_id() -> Tuple[bool, str]:
    """
    Ensure inbound_cit_ar_template_id is populated in session state.

    Resolution order:
    1. Already stored in st.session_state.st_config  → return immediately.
    2. Query GET /routes?type=TEMPLATE and match by name (exact, then
       case-insensitive).  Store the found ID and return.
    3. If still not found, return (False, descriptive error with available names).
    """
    live = _st_cfg()

    # Fast path: ID is already stored
    if live.get("inbound_cit_ar_template_id"):
        return True, live["inbound_cit_ar_template_id"]

    tmpl_name  = live.get("inbound_cit_ar_template", "Route to internal users shares")
    client_tmp = STApiClient(live["base_url"], live["api_key"], live["verify_ssl"])
    ok, result = client_tmp.get_route_templates()

    if not ok:
        err = result.get("error") or f"HTTP {result.get('status_code')}"
        return False, f"Could not query templates from server: {err}"

    raw   = result.get("data", {})
    items = (
        raw.get("result", []) if isinstance(raw, dict)
        else (raw if isinstance(raw, list) else [])
    )
    templates = [t for t in items if isinstance(t, dict)]

    # 1. Exact match
    for t in templates:
        if t.get("name") == tmpl_name:
            found_id = t.get("id", "")
            st.session_state.st_config["inbound_cit_ar_template_id"] = found_id
            return True, found_id

    # 2. Case-insensitive match
    tmpl_lower = tmpl_name.lower()
    for t in templates:
        if t.get("name", "").lower() == tmpl_lower:
            found_id = t.get("id", "")
            st.session_state.st_config["inbound_cit_ar_template_id"] = found_id
            st.session_state.st_config["inbound_cit_ar_template"]    = t.get("name", tmpl_name)
            return True, found_id

    # 3. Stripped + case-insensitive match (handles leading/trailing whitespace
    #    in template names as stored on the ST server)
    tmpl_stripped = tmpl_name.strip().lower()
    for t in templates:
        if t.get("name", "").strip().lower() == tmpl_stripped:
            found_id = t.get("id", "")
            st.session_state.st_config["inbound_cit_ar_template_id"] = found_id
            st.session_state.st_config["inbound_cit_ar_template"]    = t.get("name", tmpl_name)
            return True, found_id

    # 3. Not found — build a helpful error showing what IS available
    available = [t.get("name", "(unnamed)") for t in templates]
    if available:
        names_html = "".join(f"<li><code>{n}</code></li>" for n in available)
        msg = (
            f"Template <strong>{tmpl_name}</strong> was not found on the server. "
            f"Available templates:<ul>{names_html}</ul>"
            f"Update the template name in <strong>Admin Configuration → Inbound (CIT) Defaults</strong>."
        )
    else:
        msg = (
            "No TEMPLATE routes exist on this SecureTransport server. "
            "Create an Advanced Routing Package Template in ST first."
        )
    return False, msg

# ------------------------------------------------------------------
# Helper: render a step result in the execution log
# ------------------------------------------------------------------
def _fetch_sit_pull_template_id() -> Tuple[bool, str]:
    """Resolve the SIT_PULL AR template ID — mirrors _fetch_ar_template_id()."""
    live = _st_cfg()
    if live.get("sit_pull_ar_template_id"):
        return True, live["sit_pull_ar_template_id"]

    tmpl_name  = live.get("sit_pull_ar_template", "Send_To_Sharepoint")
    client_tmp = STApiClient(live["base_url"], live["api_key"], live["verify_ssl"])
    ok, result = client_tmp.get_route_templates()
    if not ok:
        err = result.get("error") or f"HTTP {result.get('status_code')}"
        return False, f"Could not query templates from server: {err}"

    raw   = result.get("data", {})
    items = raw.get("result", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    templates = [t for t in items if isinstance(t, dict)]

    tmpl_stripped = tmpl_name.strip().lower()
    for t in templates:
        if t.get("name", "").strip().lower() == tmpl_stripped:
            found_id = t.get("id", "")
            st.session_state.st_config["sit_pull_ar_template_id"] = found_id
            st.session_state.st_config["sit_pull_ar_template"]    = t.get("name", tmpl_name)
            return True, found_id

    available = [t.get("name", "(unnamed)") for t in templates]
    names_html = "".join(f"<li><code>{n}</code></li>" for n in available) if available else "<li><em>none</em></li>"
    return False, (
        f"Template <strong>{tmpl_name}</strong> was not found on the server. "
        f"Available templates:<ul>{names_html}</ul>"
        f"Update the template name in <strong>Admin Configuration → Pull (SIT Pull) Defaults</strong>."
    )


def _render_step(container, step_num: int, label: str, success: bool, result: dict):
    http_code = result.get("status_code", "N/A")
    url = result.get("url", "")
    error = result.get("error", "")

    bg     = "#E8F7F3" if success else "#FDECEA"
    border = "#00A0CC" if success else "#D22630"
    status = "OK" if success else "FAIL"

    with container:
        st.markdown(
            f'<div style="background:{bg};border-left:4px solid {border};'
            f'padding:8px 14px;border-radius:4px;margin:6px 0;'
            f'font-weight:600;color:#22272B;font-size:0.92rem;">'
            f'Step {step_num}: {label} &nbsp;|&nbsp; HTTP {http_code} &nbsp;[{status}]'
            f'</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=False):
            if url:
                st.markdown(
                    f'<p style="margin:2px 0 4px 4px;font-size:0.83rem;color:#4A4F54;">'
                    f'<strong>URL:</strong> <code>{url}</code></p>',
                    unsafe_allow_html=True,
                )
            req = result.get("_request_payload")
            if req:
                safe_req = json.loads(json.dumps(req))
                _mask_passwords(safe_req)
                st.markdown("**Request sent:**")
                st.json(safe_req)
            if error:
                st.error(error)
            data = result.get("data")
            if data is not None and data != "" and data != {}:
                st.markdown("**Response:**")
                st.json(data)
            if not success:
                hints = {
                    403: (
                        "HTTP 403 from the ST routes endpoint typically means one of:<br>"
                        "1. The route template is scoped to a specific Business Unit and is not "
                        "visible to the newly created account — make the template globally "
                        "accessible in ST Admin.<br>"
                        "2. The subscription ID was not captured correctly (check 'subscriptions' "
                        "in the request above).<br>"
                        "3. The Admin service may need a restart (see ST error message)."
                    ),
                    401: "HTTP 401 — API key is invalid or lacks Admin API access.",
                    404: "HTTP 404 — a referenced resource (account, template, subscription) was not found.",
                    400: "HTTP 400 — the request payload is invalid. Review the request sent above.",
                }
                hint = hints.get(http_code)
                if hint:
                    st.markdown(
                        f'<div style="background:#FFF8E1;border-left:3px solid #F5A623;'
                        f'padding:8px 12px;border-radius:4px;font-size:0.82rem;'
                        f'color:#7A5000;margin-top:6px;line-height:1.6;">{hint}</div>',
                        unsafe_allow_html=True,
                    )


def _mask_passwords(obj: Any) -> None:
    """Recursively replace password values with '***' for safe display."""
    if isinstance(obj, dict):
        for key in obj:
            if "password" in key.lower() or "secret" in key.lower():
                obj[key] = "***"
            else:
                _mask_passwords(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            _mask_passwords(item)


# ==================================================================
# Section 1: Account Information
# ==================================================================
st.subheader("1. Account Information")

acct_col1, acct_col2 = st.columns(2)
with acct_col1:
    account_name = st.text_input(
        "Account Name *",
        value="partner-acme",
        help=(
            "Unique identifier for this ST account. "
            "Use lowercase letters, numbers, and hyphens only. "
            "This becomes the login name and is used to name the application, "
            "subscription, and home folder."
        ),
    )
    email = st.text_input(
        "Email Address *",
        value="ops@acme.example.com",
        help="Contact email for this account. Used for notifications.",
    )
    account_password = st.text_input(
        "Account Password",
        type="password",
        help=(
            "Password for the ST account. Required for Inbound (CIT) flows where the "
            "partner logs in directly. For Pull (SIT) flows leave blank to auto-generate "
            "a secure password — the partner never needs to log in to ST."
        ),
    )
    confirm_password = st.text_input(
        "Confirm Password",
        type="password",
        help="Leave blank when auto-generating the password.",
    )

with acct_col2:
    change_request = st.text_input(
        "Change Request Number *",
        value="CHG0012345",
        help="Reference to the change/service request that authorised this onboarding.",
    )
    notes = st.text_area(
        "Notes / Description",
        value="Demo partner account for ACME Corp. Inbound CIT flow with internal routing.",
        height=120,
        help="Free-text notes stored as a custom property on the account.",
    )

st.divider()

# ==================================================================
# Section 2: Transfer Flow Configuration
# ==================================================================
st.subheader("2. Transfer Flow Configuration")

FLOW_OPTIONS = {
    "INBOUND_CIT": "Inbound (CIT) — Partner connects to ST and uploads files, routed to internal recipient",
    "SIT_PULL":    "Pull (SIT Pull) — ST retrieves files from partner system",
}

flow_type = st.radio(
    "Flow Type *",
    options=list(FLOW_OPTIONS.keys()),
    format_func=lambda k: FLOW_OPTIONS[k],
    help=(
        "CIT = client-initiated (partner is the client, uploads to ST). "
        "SIT Pull = server-initiated pull (ST is the client, retrieves files from partner)."
    ),
)

# Initialise all variables so references in the plan builder never fail
deliver_to       = "internal_user_account"
recipient_email  = "internal_email@yourdomain.com"
protocol         = None
remote_host      = ""
remote_port      = 22
remote_username  = ""
remote_password  = ""
download_folder  = "/"
verify_cert      = False
active_mode      = False
sftp_auth_method = "Password"   # "Password" | "SSH Key"

# -- Inbound (CIT): routing destination fields (sub-configuration of the flow) --
if flow_type == "INBOUND_CIT":
    st.markdown(
        '<div style="background:#F3ECE3;border-left:4px solid #00A0CC;'
        'padding:10px 14px;border-radius:4px;margin:10px 0 6px 0;'
        'font-size:0.9rem;color:#4A4F54;">'
        'Files uploaded by the partner are routed to an internal recipient\'s share '
        'and an email notification is sent. '
        'These values are stored as <code>additionalAttributes</code> on the account '
        'and read by the Advanced Routing template at runtime.</div>',
        unsafe_allow_html=True,
    )
    cit_col1, cit_col2 = st.columns(2)
    with cit_col1:
        deliver_to = st.text_input(
            "Internal Recipient (deliverTo) *",
            value="internal_user_account",
            help=(
                "Username or share path of the internal user who will receive the files. "
                "Stored as account additionalAttribute: deliverTo."
            ),
        )
    with cit_col2:
        recipient_email = st.text_input(
            "Recipient Email (recipientEmail) *",
            value="internal_user@yourdomain.com",
            help=(
                "Email address to notify when a file arrives. "
                "Stored as account additionalAttribute: recipientEmail."
            ),
        )

    # Show the effective Advanced Routing configuration that will be used
    _live = _st_cfg()
    _ar_app      = _live.get("inbound_cit_ar_app", "AdvRoutingApp")
    _ar_tmpl     = _live.get("inbound_cit_ar_template", "Route to internal users shares")
    _ar_tmpl_id  = _live.get("inbound_cit_ar_template_id", "")
    _id_badge = (
        f'<code style="background:#d4f1e8;padding:1px 6px;border-radius:3px;">'
        f'ID: {_ar_tmpl_id}</code>'
        if _ar_tmpl_id
        else '<span style="color:#7F8184;font-style:italic;">ID will be resolved automatically on Preview / Execute</span>'
    )
    st.markdown(
        f'<div style="background:#F3ECE3;border-left:4px solid #00A0CC;'
        f'padding:8px 14px;border-radius:4px;margin:8px 0;font-size:0.85rem;color:#4A4F54;">'
        f'{icon_img(ICO_ADMIN, 14)}'
        f'<strong>AR Application:</strong> <code>{_ar_app}</code>&nbsp;&nbsp;'
        f'{icon_img(ICO_PIN, 14)}'
        f'<strong>Template:</strong> <code>{_ar_tmpl}</code>&nbsp;&nbsp;{_id_badge}'
        f'</div>',
        unsafe_allow_html=True,
    )

# -- SIT_PULL: informational banner --
if flow_type == "SIT_PULL":
    st.markdown(
        '<div style="background:#F3ECE3;border-left:4px solid #00A0CC;'
        'padding:10px 14px;border-radius:4px;margin:10px 0 6px 0;'
        'font-size:0.9rem;color:#4A4F54;">'
        'ST will connect to the partner\'s remote system and pull files into the account folder. '
        'Files are then routed via Advanced Routing to the configured destination.</div>',
        unsafe_allow_html=True,
    )
    # Show effective AR config for SIT_PULL
    _slive = _st_cfg()
    _sp_app     = _slive.get("sit_pull_ar_app",         "AdvRoutingApp")
    _sp_tmpl    = _slive.get("sit_pull_ar_template",    "Send_To_Sharepoint")
    _sp_tmpl_id = _slive.get("sit_pull_ar_template_id", "")
    _sp_id_badge = (
        f'<code style="background:#d4f1e8;padding:1px 6px;border-radius:3px;">'
        f'ID: {_sp_tmpl_id}</code>'
        if _sp_tmpl_id
        else '<span style="color:#7F8184;font-style:italic;">ID will be resolved automatically on Preview / Execute</span>'
    )
    st.markdown(
        f'<div style="background:#F3ECE3;border-left:4px solid #00A0CC;'
        f'padding:8px 14px;border-radius:4px;margin:8px 0;font-size:0.85rem;color:#4A4F54;">'
        f'{icon_img(ICO_ADMIN, 14)}'
        f'<strong>AR Application:</strong> <code>{_sp_app}</code>&nbsp;&nbsp;'
        f'{icon_img(ICO_PIN, 14)}'
        f'<strong>Template:</strong> <code>{_sp_tmpl}</code>&nbsp;&nbsp;{_sp_id_badge}'
        f'</div>',
        unsafe_allow_html=True,
    )

# SIT_PULL requires a remote pull site; INBOUND_CIT does not
needs_remote_site = flow_type == "SIT_PULL"

st.divider()

# ==================================================================
# Section 3: Partner Remote Connection Details (SIT_PULL only)
# ==================================================================
if needs_remote_site:
    st.subheader("3. Partner Remote Connection Details")

    PROTOCOL_OPTIONS = {
        "ssh":  "SFTP (SSH)",
        "ftp":  "FTP (plain)",
        "ftps": "FTPS (FTP over TLS)",
    }
    DEFAULT_PORTS = {"ssh": 22, "ftp": 21, "ftps": 21}

    proto_col, dir_col = st.columns(2)
    with proto_col:
        protocol = st.selectbox(
            "Protocol *",
            options=list(PROTOCOL_OPTIONS.keys()),
            format_func=lambda k: PROTOCOL_OPTIONS[k],
        )
    with dir_col:
        st.markdown("**Transfer Direction:** Inbound (ST pulls from partner)")

    # Pre-populate example values when SFTP is selected
    _sftp_defaults = protocol == "ssh"
    host_col, port_col = st.columns([3, 1])
    with host_col:
        remote_host = st.text_input(
            "Remote Host *",
            value="sftp.partner.example.com" if _sftp_defaults else "",
            placeholder="sftp.partner.example.com",
        )
    with port_col:
        remote_port = st.number_input(
            "Remote Port *",
            min_value=1,
            max_value=65535,
            value=DEFAULT_PORTS.get(protocol, 22),
        )

    remote_username = st.text_input(
        "Remote Username *",
        value="sftpuser" if _sftp_defaults else "",
        placeholder="sftpuser",
    )

    download_folder = st.text_input(
        "Remote Source Folder",
        value="/home/axway/download" if _sftp_defaults else "/",
        help="Path on the partner's server from which ST will retrieve files.",
    )

    # ── Authentication ────────────────────────────────────────────
    st.markdown("**Authentication**")
    if protocol == "ssh":
        sftp_auth_method = st.radio(
            "Authentication Method *",
            options=["Password", "SSH Key"],
            horizontal=True,
            help="Password sends credentials with each connection. SSH Key uses public-key authentication — more secure and recommended.",
        )
    else:
        sftp_auth_method = "Password"

    if sftp_auth_method == "Password":
        remote_password = st.text_input(
            "Remote Password *",
            type="password",
        )
    else:
        # ── SSH Key Generation ────────────────────────────────────
        _cert_name = f"{account_name.strip() or 'account'}-sftp-key"
        st.markdown(
            f'<div style="background:#F3ECE3;border-left:4px solid #00A0CC;'
            f'padding:8px 14px;border-radius:4px;margin:6px 0;font-size:0.85rem;color:#4A4F54;">'
            f'A 2048-bit RSA key pair will be generated locally. '
            f'The private key will be imported into ST under the account as certificate '
            f'<code>{_cert_name}</code> during execution (after the account is created). '
            f'Copy the public key command shown below and run it on the remote server '
            f'<strong>before</strong> clicking Execute.</div>',
            unsafe_allow_html=True,
        )

        if st.button("Generate SSH Key Pair", key="btn_gen_ssh_key"):
            _rsa = paramiko.RSAKey.generate(2048)
            _priv_buf = io.StringIO()
            _rsa.write_private_key(_priv_buf)
            st.session_state["ssh_private_key_pem"] = _priv_buf.getvalue()
            st.session_state["ssh_public_key"]      = f"{_rsa.get_name()} {_rsa.get_base64()}"
            st.session_state["ssh_cert_name"]        = _cert_name

        if st.session_state.get("ssh_public_key"):
            _pub = st.session_state["ssh_public_key"]
            ax_success(
                f"Key pair generated. Will be imported as <code>{st.session_state.get('ssh_cert_name', _cert_name)}</code> during execution.",
                icon=ICO_SUCCESS,
            )
            st.markdown("**Run this on the remote server before executing:**")
            st.code(f'echo "{_pub}" >> ~/.ssh/authorized_keys', language="bash")
            _dl1, _dl2 = st.columns(2)
            with _dl1:
                st.download_button(
                    "Download Private Key (.pem)",
                    data=st.session_state["ssh_private_key_pem"],
                    file_name=f"{_cert_name}.pem",
                    mime="text/plain",
                    help="Save now — key is only stored in this browser session.",
                )
            with _dl2:
                st.download_button(
                    "Download Public Key (.pub)",
                    data=_pub,
                    file_name=f"{_cert_name}.pub",
                    mime="text/plain",
                )
            ax_warning(
                "Download the private key now. It will not be recoverable after a page refresh."
            )
        else:
            ax_info("Click <strong>Generate SSH Key Pair</strong> to create a key pair before executing.")

    if protocol == "ftps":
        verify_cert = st.checkbox(
            "Verify Remote SSL Certificate",
            value=True,
            help="Uncheck only for dev/test environments with self-signed certificates.",
        )

    if protocol in ("ftp", "ftps"):
        active_mode = st.checkbox(
            "Use Active Mode (FTP)",
            value=False,
            help="Enable only if the remote FTP server requires active (PORT) mode.",
        )

    st.divider()

# Derive account parameters from configuration (no manual overrides)
_prefix            = _st_cfg().get("home_folder_prefix", "/files")
custom_home_folder = f"{_prefix}/{account_name}" if account_name else f"{_prefix}/<account_name>"
custom_uid         = int(_st_cfg().get("default_uid", 65534))
custom_gid         = int(_st_cfg().get("default_gid", 65534))
custom_app_name    = f"{account_name}-app" if account_name else "<account_name>-app"

st.divider()

# ==================================================================
# Section 4: Preview and Execute
# ==================================================================
st.subheader("4. Review and Execute")


def _resolve_payload(payload: Any, captured: Dict[str, str]) -> Any:
    """
    Recursively substitute '${var}' placeholders in a payload structure.

    Used so that the COMPOSITE route step can reference the subscription ID
    captured from the preceding subscription creation step.
    """
    if isinstance(payload, dict):
        return {k: _resolve_payload(v, captured) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_resolve_payload(item, captured) for item in payload]
    if isinstance(payload, str) and payload.startswith("${") and payload.endswith("}"):
        return captured.get(payload[2:-1], payload)
    return payload


def _validate_form() -> List[str]:
    """Return a list of validation error messages. Empty list = valid."""
    errs: List[str] = []
    if not account_name.strip():
        errs.append("Account Name is required.")
    elif not all(c.isalnum() or c in "-_." for c in account_name.strip()):
        errs.append(
            "Account Name should contain only letters, numbers, hyphens, underscores, or dots."
        )
    if not email.strip():
        errs.append("Email Address is required.")
    # Password is required for INBOUND_CIT (partner logs in).
    # For SIT_PULL it is server-initiated — ST owns the account and a
    # password is auto-generated when the field is left blank.
    if flow_type == "INBOUND_CIT":
        if not account_password:
            errs.append("Account Password is required.")
        if account_password != confirm_password:
            errs.append("Passwords do not match.")
    elif account_password and account_password != confirm_password:
        errs.append("Passwords do not match.")
    if not change_request.strip():
        errs.append("Change Request Number is required.")
    if flow_type == "INBOUND_CIT":
        if not deliver_to.strip():
            errs.append("Internal Recipient (deliverTo) is required for Inbound (CIT) flow.")
        if not recipient_email.strip():
            errs.append("Recipient Email (recipientEmail) is required for Inbound (CIT) flow.")
        if not _st_cfg().get("inbound_cit_ar_template_id"):
            errs.append(
                "Advanced Routing template ID could not be resolved. "
                "Check that the template name in Admin Configuration matches a template on the server."
            )
    if flow_type == "SIT_PULL":
        if not remote_host.strip():
            errs.append("Remote Host is required for the Pull flow.")
        if not remote_username.strip():
            errs.append("Remote Username is required for the Pull flow.")
        if sftp_auth_method == "Password" and not remote_password:
            errs.append("Remote Password is required when Password authentication is selected.")
        if sftp_auth_method == "SSH Key" and not st.session_state.get("ssh_private_key_pem"):
            errs.append(
                "SSH key pair has not been generated yet. "
                "Click 'Generate SSH Key Pair' in Section 3 before executing."
            )
    return errs


def _build_api_plan() -> List[Dict[str, Any]]:
    """
    Return an ordered list of API call descriptors used for preview and execution.

    Each entry: {"label", "method", "path", "payload"}
    Steps that capture a value from the API response include:
      "capture": {"var": "<name>", "path": "<dot.separated.key>"}
    Steps whose payload contains "${var}" placeholders are resolved at execution
    time via _resolve_payload() once the captured variable is available.
    """
    acct   = account_name.strip()
    prefix = _st_cfg().get("home_folder_prefix", "/files")
    home   = custom_home_folder.strip() or f"{prefix}/{acct}"
    uid    = int(custom_uid)
    gid    = int(custom_gid)

    # For SIT_PULL the partner never logs in to ST directly.
    # Auto-generate a secure password if the user left the field blank.
    _acct_password = account_password or secrets.token_urlsafe(20)

    plan: List[Dict[str, Any]] = []

    # ---- Step 1: Create Account ----------------------------------------
    acct_notes = (
        f"CR: {change_request.strip()}. {notes.strip()}"
        if notes.strip()
        else f"CR: {change_request.strip()}"
    )
    custom_props: Optional[Dict[str, str]] = None
    if flow_type == "INBOUND_CIT":
        custom_props = {
            "deliverTo":      deliver_to.strip(),
            "recipientEmail": recipient_email.strip(),
        }

    acct_payload = STApiClient.build_account_payload(
        account_name=acct,
        password=_acct_password,
        uid=uid,
        gid=gid,
        home_folder=home,
        email=email.strip() or None,
        notes=acct_notes,
        custom_properties=custom_props,
    )
    plan.append({
        "label":   f"Create account '{acct}'",
        "method":  "POST",
        "path":    "/accounts",
        "payload": acct_payload,
    })

    # ------------------------------------------------------------------
    # INBOUND_CIT: Advanced Routing workflow  (per organisation document)
    #   Step 2 → AdvancedRouting subscription  (captures sub_id)
    #   Step 3 → COMPOSITE route  (routeTemplate + subscriptions=[sub_id])
    #            The SIMPLE route is inherited from the template — no separate
    #            SIMPLE route creation is needed.
    # ------------------------------------------------------------------
    if flow_type == "INBOUND_CIT":
        ar_app         = _st_cfg().get("inbound_cit_ar_app", "AdvRoutingApp")
        tmpl_id        = _st_cfg().get("inbound_cit_ar_template_id", "")
        composite_name = f"{acct}-composite"

        # Step 2: AdvancedRouting subscription — capture its ID from the Location header
        plan.append({
            "label":   f"Create AdvancedRouting subscription for '{acct}' (app: {ar_app})",
            "method":  "POST",
            "path":    "/subscriptions",
            "payload": STApiClient.build_ar_subscription_payload(
                account_name=acct,
                folder=home,
                application_name=ar_app,
            ),
            "capture": {"var": "sub_id", "source": "location_header"},
        })

        # Step 3: COMPOSITE route — subscriptions field links the AR subscription;
        #         routing steps are inherited from the referenced template.
        plan.append({
            "label":   f"Create COMPOSITE route '{composite_name}' (template: {tmpl_id})",
            "method":  "POST",
            "path":    "/routes",
            "payload": STApiClient.build_composite_route_payload(
                route_name=composite_name,
                account_name=acct,
                route_template_id=tmpl_id,
                subscription_id="${sub_id}",   # resolved after step 2
            ),
        })

        return plan

    # ------------------------------------------------------------------
    # SIT_PULL: Pull files from remote partner system
    #   Step 2 → (SSH Key only) Import SSH private key certificate → capture cert_id
    #   Step 2/3 → SFTP/FTP transfer site (pull from partner)
    #   Step 3/4 → Basic Application
    #   Step 4/5 → Basic Subscription (PARTNER-IN pull)
    # ------------------------------------------------------------------

    pull_site_name = f"{acct}-pull-{protocol}"
    _use_key_auth  = (protocol == "ssh" and sftp_auth_method == "SSH Key")
    _cert_name     = st.session_state.get("ssh_cert_name", f"{acct}-sftp-key")
    _priv_key_pem  = st.session_state.get("ssh_private_key_pem", "")
    _ca_pwd        = _st_cfg().get("ca_password", "")

    # Step 2 (SSH key auth only): Import the locally-generated private key into ST.
    # The account must exist first — this step runs after Step 1: Create Account.
    if _use_key_auth:
        plan.append({
            "label":           f"Import SSH private key certificate '{_cert_name}' into account '{acct}'",
            "method":          "POST_MULTIPART_CERT",
            "path":            "/certificates",
            "cert_meta": {
                "name":           _cert_name,
                "account":        acct,
                "ca_password":    _ca_pwd,
                "private_key_pem": _priv_key_pem,
            },
            "capture": {"var": "cert_id", "source": "body", "path": "id"},
        })

    # Step 2/3: Pull site (partner remote)
    if protocol == "ssh":
        pull_payload = STApiClient.build_ssh_site_payload(
            site_name=pull_site_name,
            account_name=acct,
            host=remote_host.strip(),
            port=str(int(remote_port)),
            remote_username=remote_username.strip(),
            remote_password=remote_password if not _use_key_auth else None,
            ssh_key_alias="${cert_id}" if _use_key_auth else None,
            download_folder=download_folder.strip() or "/",
        )
    elif protocol in ("ftp", "ftps"):
        pull_payload = STApiClient.build_ftp_site_payload(
            site_name=pull_site_name,
            account_name=acct,
            host=remote_host.strip(),
            port=str(int(remote_port)),
            remote_username=remote_username.strip(),
            remote_password=remote_password,
            download_folder=download_folder.strip() or "/",
            active_mode=active_mode,
            is_secure=(protocol == "ftps"),
            verify_cert=verify_cert,
        )
    else:
        pull_payload = {}

    plan.append({
        "label":   f"Create pull site '{pull_site_name}' ({PROTOCOL_OPTIONS.get(protocol, protocol)})",
        "method":  "POST",
        "path":    "/sites",
        "payload": pull_payload,
    })

    # Step 3/4: AdvancedRouting Subscription — captures sub_id for the COMPOSITE route
    sp_ar_app     = _st_cfg().get("sit_pull_ar_app",         "AdvRoutingApp")
    sp_tmpl_id    = _st_cfg().get("sit_pull_ar_template_id", "")
    sp_composite  = f"{acct}-pull-composite"

    plan.append({
        "label":   f"Create AdvancedRouting subscription for '{acct}' (app: {sp_ar_app})",
        "method":  "POST",
        "path":    "/subscriptions",
        "payload": STApiClient.build_ar_subscription_payload(
            account_name=acct,
            folder=home,
            application_name=sp_ar_app,
            file_retention_period=1,
            schedules=[
                {
                    "type":         "HOURLY",
                    "startDate":    str(int(time.time() * 1000)),
                    "skipHolidays": False,
                    "tag":          "PARTNER-IN",
                    "hourlyStep":   2,
                    "hourlyType":   "PERMINUTES",
                    "endDate":      None,
                }
            ],
            transfer_configurations=[
                {
                    "tag":      "PARTNER-IN",
                    "outbound": False,
                    "site":     pull_site_name,
                }
            ],
        ),
        "capture": {"var": "sub_id", "source": "location_header"},
    })

    # Step 4/5: COMPOSITE route — links the AR template to this account via the subscription
    plan.append({
        "label":   f"Create COMPOSITE route '{sp_composite}' (template: {sp_tmpl_id})",
        "method":  "POST",
        "path":    "/routes",
        "payload": STApiClient.build_composite_route_payload(
            route_name=sp_composite,
            account_name=acct,
            route_template_id=sp_tmpl_id,
            subscription_id="${sub_id}",   # resolved after subscription step
        ),
    })

    return plan


# Protocol label map (used in plan builder; mirrors Section 3 options)
PROTOCOL_OPTIONS = {
    "ssh": "SFTP (SSH)", "ftp": "FTP (plain)", "ftps": "FTPS (FTP over TLS)",
}

# ------------------------------------------------------------------
# Preview button
# ------------------------------------------------------------------
if ax_button("Preview API Calls", ICO_SEARCH):
    # Auto-resolve AR template ID if needed (covers the "not saved" case)
    if flow_type == "INBOUND_CIT":
        _ok, _msg = _fetch_ar_template_id()
        if not _ok:
            ax_error(_msg)
            st.stop()
        elif not _st_cfg().get("inbound_cit_ar_template_id"):
            ax_error(_msg)
            st.stop()
    if flow_type == "SIT_PULL":
        _ok, _msg = _fetch_sit_pull_template_id()
        if not _ok:
            ax_error(_msg)
            st.stop()

    errs = _validate_form()
    if errs:
        for e in errs:
            st.error(e)
    else:
        plan = _build_api_plan()
        st.markdown("**The following API calls will be executed in order:**")
        for i, step in enumerate(plan, start=1):
            # Multipart cert steps expose cert_meta instead of payload
            if step["method"] == "POST_MULTIPART_CERT":
                preview_data = {k: v for k, v in step["cert_meta"].items()}
                preview_data["_note"] = "Private key transmitted as multipart/mixed body (not shown)"
                method_label = "POST (multipart/mixed)"
            else:
                preview_data = json.loads(json.dumps(step["payload"]))
                method_label = step["method"]
            _mask_passwords(preview_data)
            payload_html = json.dumps(preview_data, indent=2).replace("<", "&lt;").replace(">", "&gt;")
            title = f"Step {i}: {method_label} {step['path']}  —  {step['label']}"
            st.markdown(
                f'<details style="border:1px solid #EBECEC;border-radius:4px;'
                f'padding:4px 14px 4px 14px;margin:6px 0;">'
                f'<summary style="cursor:pointer;font-weight:600;color:#4A4F54;'
                f'list-style:none;padding:8px 0;font-size:0.9rem;">'
                f'{title}</summary>'
                f'<pre style="background:#F8F8F8;padding:12px;border-radius:4px;'
                f'overflow-x:auto;font-size:0.82rem;margin:8px 0;">'
                f'{payload_html}</pre></details>',
                unsafe_allow_html=True,
            )



st.divider()

# ------------------------------------------------------------------
# Execute button
# ------------------------------------------------------------------
if ax_button("Execute Onboarding", ICO_ROCKET, type="primary"):
    # Auto-resolve AR template ID if needed (covers the "not saved" case)
    if flow_type == "INBOUND_CIT":
        _ok, _msg = _fetch_ar_template_id()
        if not _ok:
            ax_error(_msg)
            st.stop()
    if flow_type == "SIT_PULL":
        _ok, _msg = _fetch_sit_pull_template_id()
        if not _ok:
            ax_error(_msg)
            st.stop()

    errs = _validate_form()
    if errs:
        for e in errs:
            st.error(e)
    else:
        plan = _build_api_plan()
        client = STApiClient(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            verify_ssl=cfg["verify_ssl"],
        )

        st.markdown("### Execution Log")
        log_container = st.container()
        progress = st.progress(0, text="Starting onboarding...")

        all_success = True
        results_summary: List[Tuple[str, bool, int]] = []
        captured_vars: Dict[str, str] = {}   # values captured from API responses

        for i, step in enumerate(plan):
            progress.progress(
                i / len(plan),
                text=f"Executing step {i + 1}/{len(plan)}: {step['label']} ...",
            )
            time.sleep(0.3)

            # Resolve any ${var} placeholders inserted by earlier steps.
            # Multipart cert steps have no payload dict — skip resolution.
            if step["method"] == "POST_MULTIPART_CERT":
                resolved_payload = {}
                unresolved = []
            else:
                resolved_payload = _resolve_payload(step["payload"], captured_vars)
                # Abort early if any placeholder is still unresolved — sending a
                # literal "${var}" to ST causes a NullPointerException server-side.
                raw_str = json.dumps(resolved_payload)
                unresolved = [
                    tok for tok in raw_str.split('"')
                    if tok.startswith("${") and tok.endswith("}")
                ]
            if unresolved:
                fake_result = {
                    "status_code": 0,
                    "data": None,
                    "url": "",
                    "error": (
                        f"Placeholder(s) not resolved before execution: "
                        f"{unresolved}. "
                        f"The previous step did not return the expected field. "
                        f"Expand the previous step to inspect its response."
                    ),
                    "_request_payload": resolved_payload,
                }
                _render_step(log_container, i + 1, step["label"], False, fake_result)
                results_summary.append((step["label"], False, 0))
                all_success = False
                with log_container:
                    ax_error(
                        f"Step {i + 1} aborted — unresolved placeholder(s): "
                        f"{unresolved}. Check the previous step's response.",
                        icon=ICO_STOP,
                    )
                break

            # Dispatch the request — multipart cert import uses a dedicated method
            if step["method"] == "POST_MULTIPART_CERT":
                _cm = step["cert_meta"]
                success, result = client.create_ssh_certificate(
                    account_name=_cm["account"],
                    cert_name=_cm["name"],
                    private_key_pem=_cm["private_key_pem"],
                    ca_password=_cm["ca_password"],
                )
                result["_request_payload"] = {
                    "name":    _cm["name"],
                    "type":    "ssh",
                    "usage":   "private",
                    "account": _cm["account"],
                    "_note":   "Private key transmitted as multipart/mixed body (not shown)",
                }
            else:
                success, result = client._request(step["method"], step["path"], json=resolved_payload)
                result["_request_payload"] = resolved_payload

            _render_step(log_container, i + 1, step["label"], success, result)
            results_summary.append((step["label"], success, result.get("status_code", 0)))

            # Capture a value from this step's response for use in later steps.
            # Supports three sources:
            #   location_header  — parse the last path segment of the Location header
            #                      (ST returns the created resource ID this way on 201)
            #   body (default)   — search the JSON response body for the named field,
            #                      handling direct dict, ST result-envelope, and list.
            capture_spec = step.get("capture")
            if success and capture_spec:
                found  = ""
                source = capture_spec.get("source", "body")

                if source == "location_header":
                    location = result.get("headers", {}).get("Location", "")
                    if location:
                        # Location: /api/v2.0/subscriptions/<id>  →  last path segment
                        found = location.rstrip("/").split("/")[-1]
                else:
                    data   = result.get("data")
                    field  = capture_spec["path"]

                    if isinstance(data, dict):
                        found = data.get(field, "")
                        if not found:
                            # ST sometimes wraps single objects in {"result": [{...}]}
                            wrap = data.get("result", [])
                            if isinstance(wrap, list) and wrap and isinstance(wrap[0], dict):
                                found = wrap[0].get(field, "")
                    elif isinstance(data, list) and data and isinstance(data[0], dict):
                        found = data[0].get(field, "")

                captured_vars[capture_spec["var"]] = found

                # Warn visibly if capture still yielded nothing
                if not found:
                    if source == "location_header":
                        hint = (
                            f"Step {i + 1}: the <code>Location</code> response header was absent or empty. "
                            f"ST should return a <code>Location: .../subscriptions/&lt;id&gt;</code> header "
                            f"on a successful 201 response. Expand step {i + 1} to verify the HTTP status."
                        )
                    else:
                        hint = (
                            f"Step {i + 1}: could not capture <code>{capture_spec.get('path')}</code> "
                            f"from the response body. "
                            f"Expand step {i + 1} above to inspect the full response body."
                        )
                    with log_container:
                        ax_warning(hint, icon=ICO_WARNING)

            if not success:
                all_success = False
                with log_container:
                    ax_error(
                        f"Step {i + 1} failed. Stopping execution to prevent partial configuration drift.",
                        icon=ICO_STOP,
                    )
                break

        progress.progress(1.0, text="Done.")

        st.divider()
        st.markdown("### Summary")
        for label, ok, code in results_summary:
            ico = ICO_SUCCESS if ok else ICO_ERROR
            img = icon_img(ico, 18)
            st.markdown(
                f'<div style="margin:4px 0;">{img}{label} — HTTP {code}</div>',
                unsafe_allow_html=True,
            )

        if all_success:
            ax_success(
                f"Account <strong>{account_name.strip()}</strong> onboarded successfully. "
                f"Change Request: <strong>{change_request.strip()}</strong>.",
                icon=ICO_ROCKET,
            )
        else:
            ax_error(
                "Onboarding did not complete. Review the failed step above, "
                "resolve the issue, and re-run. "
                "Objects created before the failure may need manual cleanup.",
                icon=ICO_WARNING,
            )

