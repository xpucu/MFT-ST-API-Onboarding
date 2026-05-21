"""
Admin Configuration page.

Store the ST server URL, API key, and account creation defaults
in session state so the onboarding page can use them.
Configuration is also persisted to a local .env file so values
survive browser/server restarts without re-entry.
"""

import os

import streamlit as st

from branding import (
    apply_branding, ax_success, ax_error, ax_info, ax_warning,
    icon_img, ICO_REFRESH, ICO_ADMIN, ICO_PAPERCLIP, ICO_PIN,
)
from st_api_client import STApiClient

st.set_page_config(
    page_title="Admin Configuration - ST Onboarding",
    page_icon=None,
    layout="wide",
)
apply_branding()

# Absolute path to the .env file at the project root
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def _write_env(values: dict) -> None:
    """
    Write key=value pairs to .env, merging with any existing entries.
    Existing keys are updated; unknown keys are preserved.
    Values that contain spaces or special characters are double-quoted.
    """
    # Read existing content
    existing: dict = {}
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "r") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip().strip('"')

    # Merge new values
    existing.update(values)

    # Write back
    with open(_ENV_PATH, "w") as fh:
        fh.write("# ST Onboarding Portal — auto-generated configuration\n")
        for k, v in existing.items():
            # Quote values that contain whitespace or special chars
            v_str = str(v)
            needs_quotes = any(c in v_str for c in (' ', '\t', '#', '"', "'", '\\', '='))
            fh.write(f'{k}="{v_str}"\n' if needs_quotes else f"{k}={v_str}\n")


st.title("Admin Configuration")
st.markdown(
    "Configure the connection to the **SecureTransport Admin REST API** and "
    "set the default values used when creating new accounts."
)
st.divider()

# Convenience reference to the persisted config dict
cfg: dict = st.session_state.get("st_config", {})

# ------------------------------------------------------------------
# Configuration form
# ------------------------------------------------------------------
with st.form("admin_config_form", clear_on_submit=False):

    st.subheader("Server Connection")
    col_url, col_ssl = st.columns([3, 1])
    with col_url:
        base_url = st.text_input(
            "ST Admin API Base URL",
            value=cfg.get("base_url", "https://sl3csoecd3899.pcloud.axway.int:444/api/v2.0"),
            placeholder="https://st-server.example.com:444/api/v2.0",
            help=(
                "Full base URL including the API path. "
                "Example: https://securetransport.example.com:444/api/v2.0"
            ),
        )
    with col_ssl:
        verify_ssl = st.checkbox(
            "Verify SSL certificate",
            value=cfg.get("verify_ssl", False),
            help=(
                "Enable only when the server presents a trusted CA-signed certificate. "
                "Leave unchecked for self-signed or internal certificates."
            ),
        )

    api_key = st.text_input(
        "API Key",
        type="password",
        value=cfg.get("api_key", ""),
        help=(
            "Sent as: SECURETRANSPORT-API-KEY: <key>. "
            "Saved to the local .env file on successful connection test."
        ),
    )

    st.divider()
    st.subheader("Account Creation Defaults")
    st.markdown(
        "These values are pre-filled during account onboarding. "
        "They can be overridden on a per-account basis."
    )

    col_uid, col_gid, col_prefix = st.columns(3)
    with col_uid:
        default_uid = st.number_input(
            "Default UID",
            min_value=0,
            max_value=2147483647,
            value=int(cfg.get("default_uid", 65534)),
            help=(
                "POSIX user ID assigned to new accounts. "
                "65534 (nobody) is a common default for virtual users in ST."
            ),
        )
    with col_gid:
        default_gid = st.number_input(
            "Default GID",
            min_value=0,
            max_value=2147483647,
            value=int(cfg.get("default_gid", 65534)),
            help="POSIX group ID assigned to new accounts.",
        )
    with col_prefix:
        home_folder_prefix = st.text_input(
            "Home Folder Prefix",
            value=cfg.get("home_folder_prefix", "/files"),
            placeholder="/files",
            help=(
                "The account home folder is constructed as "
                "<prefix>/<account_name>. "
                "Example: /files -> /files/partnerA"
            ),
        )

    st.divider()
    submit = st.form_submit_button("Save and Test Connection", type="primary")

# ------------------------------------------------------------------
# Handle form submission
# ------------------------------------------------------------------
if submit:
    errors = []
    if not base_url or base_url.strip() in ("https://", "http://", ""):
        errors.append("Server URL is required.")
    if not api_key.strip():
        errors.append("API Key is required.")
    if not home_folder_prefix.startswith("/"):
        errors.append("Home folder prefix must start with /.")

    if errors:
        for err in errors:
            st.error(err)
    else:
        with st.spinner("Testing connection to SecureTransport..."):
            client = STApiClient(
                base_url.strip(), api_key.strip(), verify_ssl
            )
            success, result = client.test_connection()

        if success:
            # Preserve any existing flow defaults already stored in session state
            existing = st.session_state.get("st_config", {})
            st.session_state.st_config = {
                "base_url": base_url.strip().rstrip("/"),
                "api_key": api_key.strip(),
                "verify_ssl": verify_ssl,
                "default_uid": int(default_uid),
                "default_gid": int(default_gid),
                "home_folder_prefix": home_folder_prefix.rstrip("/"),
                "configured": True,
                # Inbound (CIT) Advanced Routing defaults — preserved across saves
                "inbound_cit_ar_app": existing.get("inbound_cit_ar_app", "AdvRoutingApp"),
                "inbound_cit_ar_template": existing.get("inbound_cit_ar_template", "Route to internal users shares"),
                "inbound_cit_ar_template_id": existing.get("inbound_cit_ar_template_id", ""),
            }

            # Persist to .env so values survive restarts
            _write_env({
                "ST_BASE_URL":           base_url.strip().rstrip("/"),
                "ST_API_KEY":            api_key.strip(),
                "ST_VERIFY_SSL":         str(verify_ssl).lower(),
                "ST_DEFAULT_UID":        str(int(default_uid)),
                "ST_DEFAULT_GID":        str(int(default_gid)),
                "ST_HOME_FOLDER_PREFIX": home_folder_prefix.rstrip("/"),
            })

            ax_success(
                f"Connection successful. HTTP {result.get('status_code')}. "
                "Configuration saved to session and <code>.env</code>."
            )
        else:
            error_msg = result.get("error") or (
                f"HTTP {result.get('status_code')} - {result.get('data')}"
            )
            ax_error(f"Connection failed: {error_msg}")
            if result.get("status_code") == 401:
                ax_info(
                    "HTTP 401 indicates the API key is invalid or does not have "
                    "admin REST API access."
                )
            elif not result.get("status_code"):
                ax_info(
                    "No HTTP response received. Check the base URL and ensure the "
                    "SecureTransport admin port is reachable from this host."
                )

# ------------------------------------------------------------------
# Display current saved config (read-only, key masked)
# ------------------------------------------------------------------
st.divider()
st.subheader("Saved Configuration")
saved = st.session_state.get("st_config", {})
if saved.get("configured"):
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.markdown(f"**Base URL:** `{saved.get('base_url')}`")
        st.markdown(f"**API Key:** `{'*' * 12}`")
        st.markdown(f"**Verify SSL:** `{saved.get('verify_ssl')}`")
    with info_col2:
        st.markdown(f"**Default UID:** `{saved.get('default_uid')}`")
        st.markdown(f"**Default GID:** `{saved.get('default_gid')}`")
        st.markdown(f"**Home Folder Prefix:** `{saved.get('home_folder_prefix')}`")
    ax_success("Ready for account onboarding.")
else:
    ax_info("No configuration saved yet. Fill in the form above and click Save and Test Connection.")

# ------------------------------------------------------------------
# Inbound (CIT) — Advanced Routing Defaults
# ------------------------------------------------------------------
st.divider()

# Section header with Axway icon
st.markdown(
    f'{icon_img(ICO_ADMIN, 24)}'
    f'<span style="font-size:1.15rem;font-weight:600;color:#4A4F54;">'
    f'&nbsp;Inbound (CIT) — Advanced Routing Defaults</span>',
    unsafe_allow_html=True,
)
st.markdown(
    "Configure defaults for the extended Inbound (CIT) flow: "
    "partner uploads files to ST, files are routed to an internal destination, "
    "and the internal user receives an email notification. "
    "This flow uses an **Advanced Routing** application and subscription instead of Basic."
)

if not st.session_state.get("st_config", {}).get("configured"):
    ax_warning(
        "Save a valid server connection above before configuring flow defaults. "
        "The template list requires a live API connection."
    )
else:
    _cfg = st.session_state.st_config

    # ------------------------------------------------------------------
    # Active template banner — always visible
    # ------------------------------------------------------------------
    _active_name = _cfg.get("inbound_cit_ar_template") or "Route to internal users shares"
    _active_id   = _cfg.get("inbound_cit_ar_template_id", "")
    _is_default  = (_active_name == "Route to internal users shares"
                    and not _cfg.get("inbound_cit_ar_template_id"))

    _id_badge = (
        f'<code style="background:#d4f1e8;padding:1px 6px;border-radius:3px;">'
        f'ID: {_active_id}</code>'
        if _active_id
        else '<span style="color:#7F8184;font-style:italic;">ID not yet resolved — load templates to populate</span>'
    )
    _label = "Default" if _is_default else "Configured"
    st.markdown(
        f'<div style="background:#E8F7F3;border-left:5px solid #00A0CC;'
        f'padding:10px 14px;border-radius:4px;margin:8px 0;line-height:1.7;">'
        f'{icon_img(ICO_PIN, 16)}'
        f'<strong>Active template ({_label}):</strong>&nbsp;'
        f'<code>{_active_name}</code>&nbsp;&nbsp;{_id_badge}'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("")

    ar_col1, ar_col2 = st.columns([2, 3])

    with ar_col1:
        ar_app_name = st.text_input(
            "Advanced Routing Application",
            value=_cfg.get("inbound_cit_ar_app", "AdvRoutingApp"),
            help=(
                "Name of the AdvancedRouting application in SecureTransport. "
                "This application must already exist on the server or will be created "
                "during onboarding. Must be type=AdvancedRouting, not Basic."
            ),
        )

    with ar_col2:
        # Template selection — requires a live query
        _templates_key     = "ar_templates_list"
        _templates_map_key = "ar_templates_map"   # name -> {id, description}
        if _templates_key not in st.session_state:
            st.session_state[_templates_key] = []
        if _templates_map_key not in st.session_state:
            st.session_state[_templates_map_key] = {}

        load_col, _ = st.columns([2, 5])
        with load_col:
            load_clicked = st.button(
                "Load Templates",
                help="Query SecureTransport for available Advanced Routing TEMPLATE routes.",
            )
        st.markdown(
            f'{icon_img(ICO_REFRESH, 14)}'
            f'<span style="font-size:0.78rem;color:#7F8184;">'
            f'Queries <code>GET /routes?type=TEMPLATE</code></span>',
            unsafe_allow_html=True,
        )

        if load_clicked:
            with st.spinner("Loading Advanced Routing templates..."):
                _client = STApiClient(
                    _cfg["base_url"], _cfg["api_key"], _cfg["verify_ssl"]
                )
                _ok, _result = _client.get_route_templates()

            if _ok:
                _raw = _result.get("data", {})
                # ST list response: {"result": [...], "resultSet": {...}}
                _items = (
                    _raw.get("result", [])
                    if isinstance(_raw, dict)
                    else (_raw if isinstance(_raw, list) else [])
                )
                _names = [t.get("name", t.get("id", str(t))) for t in _items if isinstance(t, dict)]
                # Store full detail per template: id + description
                _tmap = {
                    t.get("name", t.get("id", str(t))): {
                        "id":          t.get("id", ""),
                        "description": t.get("description", ""),
                    }
                    for t in _items if isinstance(t, dict)
                }
                st.session_state[_templates_key]     = _names
                st.session_state[_templates_map_key] = _tmap

                # Auto-resolve the ID for the currently active template
                # Use stripped + case-insensitive comparison to tolerate
                # whitespace in server-side template names.
                _cur_name = _cfg.get("inbound_cit_ar_template", "").strip().lower()
                for _tname, _tdetail in _tmap.items():
                    if _tname.strip().lower() == _cur_name:
                        st.session_state.st_config["inbound_cit_ar_template_id"] = _tdetail["id"]
                        break

                if _names:
                    ax_success(f"Loaded {len(_names)} template(s).")
                else:
                    ax_info(
                        "No TEMPLATE routes found on this server. "
                        "Create an Advanced Routing template in SecureTransport first."
                    )
            else:
                _err = _result.get("error") or f"HTTP {_result.get('status_code')}"
                ax_error(f"Failed to load templates: {_err}")

        _template_list     = st.session_state.get(_templates_key, [])
        _template_map      = st.session_state.get(_templates_map_key, {})
        _saved_template    = _cfg.get("inbound_cit_ar_template", "Route to internal users shares")

        if _template_list:
            # Determine the index of the previously saved selection
            _idx = 0
            if _saved_template in _template_list:
                _idx = _template_list.index(_saved_template)
            ar_template = st.selectbox(
                "Advanced Routing Template",
                options=_template_list,
                index=_idx,
                help=(
                    "The TEMPLATE route that owns the routing logic for this flow. "
                    "It is linked to the COMPOSITE route created during onboarding."
                ),
            )
            # Show description + ID of the selected template
            _sel_detail = _template_map.get(ar_template, {})
            _sel_desc   = _sel_detail.get("description", "")
            _sel_id     = _sel_detail.get("id", "")
            _desc_text  = _sel_desc if _sel_desc else "<em>No description set for this template.</em>"
            _id_text    = (
                f'<code style="background:#d4f1e8;padding:1px 5px;border-radius:3px;">'
                f'ID: {_sel_id}</code>'
                if _sel_id else
                '<span style="color:#7F8184;font-style:italic;">ID unavailable</span>'
            )
            st.markdown(
                f'<div style="margin-top:4px;padding:8px 12px;background:#E6F4F8;'
                f'border-left:3px solid #00A0CC;border-radius:4px;'
                f'font-size:0.85rem;color:#006580;line-height:1.6;">'
                f'{icon_img(ICO_PAPERCLIP, 14)}{_desc_text}'
                f'<br>{_id_text}</div>',
                unsafe_allow_html=True,
            )
        else:
            ar_template = st.text_input(
                "Advanced Routing Template",
                value=_saved_template,
                placeholder="Click 'Load Templates' to populate this list",
                help=(
                    "Enter the template name manually, or click 'Load Templates' "
                    "to query available templates from the server."
                ),
            )

    st.markdown("")  # visual spacer

    save_cit_col, _ = st.columns([3, 9])
    with save_cit_col:
        if st.button("Save Inbound (CIT) Defaults", type="primary"):
            if not ar_app_name.strip():
                ax_error("Advanced Routing Application name cannot be empty.")
            else:
                _chosen_name = ar_template.strip() if isinstance(ar_template, str) else ar_template
                _tmap_now    = st.session_state.get(_templates_map_key, {})

                # Prefer the ID from the loaded template map; fall back to
                # whatever is already stored so a Save without loading templates
                # never silently overwrites a valid ID with an empty string.
                _existing_id = st.session_state.st_config.get("inbound_cit_ar_template_id", "")
                _found_id    = _tmap_now.get(_chosen_name, {}).get("id", "")
                _chosen_id   = _found_id or _existing_id

                st.session_state.st_config["inbound_cit_ar_app"]         = ar_app_name.strip()
                st.session_state.st_config["inbound_cit_ar_template"]    = _chosen_name
                st.session_state.st_config["inbound_cit_ar_template_id"] = _chosen_id

                # Persist AR defaults to .env
                _write_env({
                    "ST_CIT_AR_APP":         ar_app_name.strip(),
                    "ST_CIT_AR_TEMPLATE":    _chosen_name,
                    "ST_CIT_AR_TEMPLATE_ID": _chosen_id,
                })

                _id_note = f"ID: <code>{_chosen_id}</code>" if _chosen_id else (
                    "ID not yet resolved — click 'Load Templates' first to populate it"
                )
                ax_success(
                    f"Inbound (CIT) defaults saved to session and <code>.env</code>. "
                    f"Application: <strong>{ar_app_name.strip()}</strong> | "
                    f"Template: <strong>{_chosen_name or '(none)'}</strong> — {_id_note}"
                )

# ------------------------------------------------------------------
# Pull (SIT Pull) — Advanced Routing Defaults
# ------------------------------------------------------------------
st.divider()

st.markdown(
    f'{icon_img(ICO_ADMIN, 24)}'
    f'<span style="font-size:1.15rem;font-weight:600;color:#4A4F54;">'
    f'&nbsp;Pull (SIT Pull) — Advanced Routing Defaults</span>',
    unsafe_allow_html=True,
)
st.markdown(
    "Configure defaults for the Pull to SharePoint flow: "
    "ST pulls files from a remote partner and routes them via an "
    "**Advanced Routing** application and template."
)

if not st.session_state.get("st_config", {}).get("configured"):
    ax_warning(
        "Save a valid server connection above before configuring flow defaults. "
        "The template list requires a live API connection."
    )
else:
    _pcfg = st.session_state.st_config

    # Active template banner
    _p_name = _pcfg.get("sit_pull_ar_template") or "Send_To_Sharepoint"
    _p_id   = _pcfg.get("sit_pull_ar_template_id", "")
    _p_is_default = (_p_name == "Send_To_Sharepoint" and not _p_id)
    _p_id_badge = (
        f'<code style="background:#d4f1e8;padding:1px 6px;border-radius:3px;">'
        f'ID: {_p_id}</code>'
        if _p_id
        else '<span style="color:#7F8184;font-style:italic;">ID not yet resolved — load templates to populate</span>'
    )
    st.markdown(
        f'<div style="background:#E8F7F3;border-left:5px solid #00A0CC;'
        f'padding:10px 14px;border-radius:4px;margin:8px 0;line-height:1.7;">'
        f'{icon_img(ICO_PIN, 16)}'
        f'<strong>Active template ({"Default" if _p_is_default else "Configured"}):</strong>&nbsp;'
        f'<code>{_p_name}</code>&nbsp;&nbsp;{_p_id_badge}'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("")

    _p_col1, _p_col2 = st.columns([2, 3])

    with _p_col1:
        pull_ar_app_name = st.text_input(
            "Advanced Routing Application",
            value=_pcfg.get("sit_pull_ar_app", "AdvRoutingApp"),
            key="pull_ar_app_input",
            help="Name of the AdvancedRouting application in SecureTransport for the Pull flow.",
        )

    with _p_col2:
        _p_tlist_key = "pull_ar_templates_list"
        _p_tmap_key  = "pull_ar_templates_map"
        if _p_tlist_key not in st.session_state:
            st.session_state[_p_tlist_key] = []
        if _p_tmap_key not in st.session_state:
            st.session_state[_p_tmap_key] = {}

        _p_load_col, _ = st.columns([2, 5])
        with _p_load_col:
            _p_load_clicked = st.button(
                "Load Templates",
                key="pull_load_templates",
                help="Query SecureTransport for available Advanced Routing TEMPLATE routes.",
            )
        st.markdown(
            f'{icon_img(ICO_REFRESH, 14)}'
            f'<span style="font-size:0.78rem;color:#7F8184;">'
            f'Queries <code>GET /routes?type=TEMPLATE</code></span>',
            unsafe_allow_html=True,
        )

        if _p_load_clicked:
            with st.spinner("Loading Advanced Routing templates..."):
                _p_client = STApiClient(_pcfg["base_url"], _pcfg["api_key"], _pcfg["verify_ssl"])
                _p_ok, _p_result = _p_client.get_route_templates()

            if _p_ok:
                _p_raw   = _p_result.get("data", {})
                _p_items = (
                    _p_raw.get("result", []) if isinstance(_p_raw, dict)
                    else (_p_raw if isinstance(_p_raw, list) else [])
                )
                _p_names = [t.get("name", t.get("id", str(t))) for t in _p_items if isinstance(t, dict)]
                _p_tmap  = {
                    t.get("name", t.get("id", str(t))): {
                        "id":          t.get("id", ""),
                        "description": t.get("description", ""),
                    }
                    for t in _p_items if isinstance(t, dict)
                }
                st.session_state[_p_tlist_key] = _p_names
                st.session_state[_p_tmap_key]  = _p_tmap

                # Auto-resolve ID for the currently active template
                _p_cur = _pcfg.get("sit_pull_ar_template", "").strip().lower()
                for _tn, _td in _p_tmap.items():
                    if _tn.strip().lower() == _p_cur:
                        st.session_state.st_config["sit_pull_ar_template_id"] = _td["id"]
                        break

                ax_success(f"Loaded {len(_p_names)} template(s).") if _p_names else ax_info(
                    "No TEMPLATE routes found on this server."
                )
            else:
                _p_err_msg = _p_result.get('error') or f"HTTP {_p_result.get('status_code')}"
                ax_error(f"Failed to load templates: {_p_err_msg}")

        _p_tlist   = st.session_state.get(_p_tlist_key, [])
        _p_tmap    = st.session_state.get(_p_tmap_key, {})
        _p_saved   = _pcfg.get("sit_pull_ar_template", "Send_To_Sharepoint")

        if _p_tlist:
            _p_idx = _p_tlist.index(_p_saved) if _p_saved in _p_tlist else 0
            pull_ar_template = st.selectbox(
                "Advanced Routing Template",
                options=_p_tlist,
                index=_p_idx,
                key="pull_ar_template_select",
                help="TEMPLATE route that defines the routing logic for the Pull flow.",
            )
            _p_sel = _p_tmap.get(pull_ar_template, {})
            _p_desc = _p_sel.get("description", "") or "<em>No description set.</em>"
            _p_sel_id = _p_sel.get("id", "")
            st.markdown(
                f'<div style="margin-top:4px;padding:8px 12px;background:#E6F4F8;'
                f'border-left:3px solid #00A0CC;border-radius:4px;'
                f'font-size:0.85rem;color:#006580;line-height:1.6;">'
                f'{icon_img(ICO_PAPERCLIP, 14)}{_p_desc}<br>'
                f'{"<code style=\"background:#d4f1e8;padding:1px 5px;border-radius:3px;\">ID: " + _p_sel_id + "</code>" if _p_sel_id else "<span style=\"color:#7F8184;font-style:italic;\">ID unavailable</span>"}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            pull_ar_template = st.text_input(
                "Advanced Routing Template",
                value=_p_saved,
                key="pull_ar_template_text",
                placeholder="Click 'Load Templates' to populate this list",
            )

    st.markdown("")

    _p_save_col, _ = st.columns([3, 9])
    with _p_save_col:
        if st.button("Save Pull (SIT Pull) Defaults", type="primary", key="pull_save_btn"):
            if not pull_ar_app_name.strip():
                ax_error("Advanced Routing Application name cannot be empty.")
            else:
                _p_chosen = pull_ar_template.strip() if isinstance(pull_ar_template, str) else pull_ar_template
                _p_tmap_now = st.session_state.get(_p_tmap_key, {})
                _p_existing_id = st.session_state.st_config.get("sit_pull_ar_template_id", "")
                _p_found_id    = _p_tmap_now.get(_p_chosen, {}).get("id", "")
                _p_chosen_id   = _p_found_id or _p_existing_id

                st.session_state.st_config["sit_pull_ar_app"]         = pull_ar_app_name.strip()
                st.session_state.st_config["sit_pull_ar_template"]    = _p_chosen
                st.session_state.st_config["sit_pull_ar_template_id"] = _p_chosen_id

                _write_env({
                    "ST_SIT_PULL_AR_APP":         pull_ar_app_name.strip(),
                    "ST_SIT_PULL_AR_TEMPLATE":    _p_chosen,
                    "ST_SIT_PULL_AR_TEMPLATE_ID": _p_chosen_id,
                })

                _p_id_note = f"ID: <code>{_p_chosen_id}</code>" if _p_chosen_id else (
                    "ID not yet resolved — click 'Load Templates' first"
                )
                ax_success(
                    f"Pull (SIT Pull) defaults saved. "
                    f"Application: <strong>{pull_ar_app_name.strip()}</strong> | "
                    f"Template: <strong>{_p_chosen or '(none)'}</strong> — {_p_id_note}"
                )

