"""
Axway SecureTransport - Account Onboarding Portal
Home / landing page.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from branding import apply_branding, ax_success, ax_warning

st.set_page_config(
    page_title="ST Account Onboarding",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_branding()

# ------------------------------------------------------------------
# Load persisted config from .env (written by Admin Configuration)
# ------------------------------------------------------------------
_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH, override=False)   # does not overwrite existing OS env vars

# Initialise session state defaults once per session
if "st_config" not in st.session_state:
    _from_env = os.environ.get("ST_BASE_URL", "")
    st.session_state.st_config = {
        "base_url":             os.environ.get("ST_BASE_URL",          "https://your-st-server:444/api/v2.0"),
        "api_key":              os.environ.get("ST_API_KEY",           ""),
        "verify_ssl":           os.environ.get("ST_VERIFY_SSL",        "false").lower() == "true",
        "default_uid":          int(os.environ.get("ST_DEFAULT_UID",   "65534")),
        "default_gid":          int(os.environ.get("ST_DEFAULT_GID",   "65534")),
        "home_folder_prefix":   os.environ.get("ST_HOME_FOLDER_PREFIX", "/files"),
        "ca_password":          os.environ.get("CA_PASSWORD",          ""),
        "configured":           bool(_from_env),
        # Inbound (CIT) Advanced Routing defaults
        "inbound_cit_ar_app":          os.environ.get("ST_CIT_AR_APP",              "AdvRoutingApp"),
        "inbound_cit_ar_template":     os.environ.get("ST_CIT_AR_TEMPLATE",         "Route to internal users shares"),
        "inbound_cit_ar_template_id":  os.environ.get("ST_CIT_AR_TEMPLATE_ID",      ""),
        # Pull (SIT Pull) Advanced Routing defaults
        "sit_pull_ar_app":             os.environ.get("ST_SIT_PULL_AR_APP",         "AdvRoutingApp"),
        "sit_pull_ar_template":        os.environ.get("ST_SIT_PULL_AR_TEMPLATE",    "Send_To_Sharepoint"),
        "sit_pull_ar_template_id":     os.environ.get("ST_SIT_PULL_AR_TEMPLATE_ID", ""),
    }

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
st.title("Axway SecureTransport — Account Onboarding Portal")

st.image(
    os.path.join(os.path.dirname(__file__), "resources", "Axway_Banner_640x240_EN_4_2026.jpg"),
    use_container_width=False,
)

st.markdown(
    "A Streamlit web application that automates partner account onboarding on "
    "**Axway SecureTransport** using the ST Admin REST API v2.0."
)

st.divider()

st.markdown(
    """
> ### IMPORTANT NOTICE — PROOF OF CONCEPT
>
> **This project is provided as a proof of concept and example only.**
>
> It was created to demonstrate how the Axway SecureTransport Admin REST API can
> be used to automate account onboarding workflows. It is **not** a production-ready
> tool and has not been hardened, security-reviewed, or validated for use in
> production environments.
>
> - **Use at your own risk.** Review and adapt all code to your organisation's
>   security policies, infrastructure, and operational requirements before deploying
>   in any environment.
> - **No guarantees.** This software is provided "as-is" without warranty of any
>   kind, express or implied, including but not limited to fitness for a particular
>   purpose or correctness of results.
> - **No support.** Axway does not provide support for this project through any
>   official support channel.
> - **No maintenance commitment.** Axway will not maintain, update, or patch this
>   project. It may become outdated as SecureTransport evolves.
> - **Not an Axway product.** This is an independent example and does not represent
>   an officially released or endorsed Axway product, feature, or service.
>
> This code was authored by **Axway Professional Services** and is published as a
> reference and example of SecureTransport Admin REST API usage.
"""
)

st.divider()

st.markdown(
    """
**Attributions**

- **[Axway SecureTransport](https://www.axway.com/en/products/managed-file-transfer/secure-transport)**
  — Managed File Transfer platform by Axway. All SecureTransport product names,
  trademarks, and API definitions referenced in this project are the property of Axway Inc.
- **[Streamlit](https://streamlit.io)** — Open-source Python framework used to build the
  web interface. Streamlit is a product of Snowflake Inc. and is licensed under the
  Apache License 2.0.
"""
)

st.divider()

st.markdown(
    """
Use the sidebar to navigate between pages:

| Page | Purpose |
|------|---------|
| **Admin Configuration** | Configure the ST server URL and admin credentials, set account defaults |
| **Account Onboarding** | Create an account, define the transfer flow type, generate all required API objects |
"""
)

st.divider()

# ------------------------------------------------------------------
# Connection status banner
# ------------------------------------------------------------------
cfg = st.session_state.st_config
if cfg.get("configured"):
    ax_success(
        f"Connected to <strong>{cfg['base_url']}</strong>. "
        "Proceed to Account Onboarding."
    )
else:
    ax_warning(
        "No SecureTransport server configured yet. "
        "Go to <strong>Admin Configuration</strong> first."
    )

st.divider()

# ------------------------------------------------------------------
# Workflow overview
# ------------------------------------------------------------------
st.subheader("Supported Onboarding Flows")

flow_col1, flow_col2 = st.columns(2)

with flow_col1:
    st.markdown(
        """
**Inbound (CIT)**

The partner connects to ST over any supported and enabled inbound protocol and
uploads files to their subscription folder. ST triggers Advanced Routing to
deliver the files to an internal recipient and send an email notification.
The `deliverTo` and `recipientEmail` attributes are stored on the account and
read by the AR template at runtime.

*API objects created:*
- Account (with `deliverTo` and `recipientEmail` additionalAttributes)
- AdvancedRouting Subscription
- COMPOSITE Route (linked to the configured AR template)
"""
    )

with flow_col2:
    st.markdown(
        """
**Pull (SIT Pull)**

ST connects to the partner's remote SFTP or FTP server on a schedule (every
2 minutes by default), retrieves files, and routes them through Advanced Routing.
When SSH Key authentication is selected, a 2048-bit RSA key pair is generated
locally and the private key is imported into the ST account before the site
is created.

*API objects created:*
- Account
- SSH Private Key Certificate (SSH Key auth only)
- Pull Transfer Site (SFTP or FTP)
- AdvancedRouting Subscription (with pull schedule and pull-history deduplication)
- COMPOSITE Route (linked to the configured AR template)
"""
    )

st.divider()
st.caption(
    "Axway SecureTransport Admin REST API v2.0  |  "
    "For questions, consult the README or your SecureTransport admin."
)

