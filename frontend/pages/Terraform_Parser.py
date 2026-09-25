"""Terraform Parser — onboarding demo page.

Calls the backend at /api/parse-terraform/sample, renders the parsed
resources as a card grid, and exposes a button to ingest the parse
into the RAG knowledge base.

This page is the stage demo for "any company can onboard in minutes":
point at Terraform, get a dependency graph, no YAML required.
"""
import html

import streamlit as st

from api_client import get_json_detailed
from style import apply_style, sidebar, empty_state


st.set_page_config(
    page_title="Terraform Parser | Spectre",
    page_icon="🧱",
    layout="wide",
)
apply_style()
sidebar("Terraform Parser")

st.title("🧱 Terraform Parser")
st.caption(
    "Point Spectre at a folder of Terraform files. It builds the "
    "dependency graph automatically — no YAML required."
)

if "tf_parse_result" not in st.session_state:
    st.session_state.tf_parse_result = None

col_parse, col_rag, _ = st.columns([1, 1, 3])

with col_parse:
    parse_clicked = st.button(
        "🔄 Parse demo Terraform",
        use_container_width=True,
        help="Re-parse the bundled demo_terraform/ directory.",
    )

with col_rag:
    rag_clicked = st.button(
        "📚 Parse + add to RAG",
        use_container_width=True,
        help="Parse and add every resource to the knowledge base.",
    )

if st.session_state.tf_parse_result is None:
    ok, data, _ = get_json_detailed("/api/parse-terraform/sample", timeout=30)
    if ok:
        st.session_state.tf_parse_result = data

if parse_clicked:
    with st.spinner("Parsing Terraform..."):
        ok, data, _ = get_json_detailed("/api/parse-terraform/sample", timeout=30)
    if ok:
        st.session_state.tf_parse_result = data
        st.success("Graph rebuilt from the demo Terraform directory.")
    else:
        st.warning(data.get("message") or data.get("error") or "Parse failed.")

if rag_clicked:
    with st.spinner("Parsing and ingesting into the knowledge base..."):
        ok, data, _ = get_json_detailed(
            "/api/parse-terraform/sample?add_to_rag=true",
            timeout=60,
        )
    if ok:
        st.session_state.tf_parse_result = data
        added = data.get("rag_documents_added", 0)
        st.success(f"Added {added} resource(s) to the knowledge base.")
    else:
        st.warning(data.get("message") or data.get("error") or "RAG ingest failed.")

data = st.session_state.tf_parse_result
if not data:
    st.markdown(
        empty_state(
            "🧱",
            "No parse result",
            "The backend did not return a graph. Check that uvicorn is running.",
        ),
        unsafe_allow_html=True,
    )
    st.stop()

meta = data.get("meta") or {}
nodes = data.get("nodes") or {}
edges = data.get("edges") or []

m1, m2, m3, m4 = st.columns(4)
m1.metric("Files parsed", meta.get("files_parsed", 0))
m2.metric("Resources found", meta.get("resources_found", 0))
m3.metric("Dependency edges", len(edges))
m4.metric("Source", meta.get("source", "—"))

st.divider()
st.subheader("Parsed resources")

TYPE_COLORS = {
    "database": "#7c3aed",
    "cache": "#0891b2",
    "service": "#059669",
    "api": "#ea580c",
    "frontend": "#dc2626",
    "network": "#6b7280",
    "storage": "#ca8a04",
    "unknown": "#4b5563",
}
TYPE_ORDER = {
    "network": 0, "storage": 1, "database": 2, "cache": 3,
    "service": 4, "api": 5, "frontend": 6, "unknown": 7,
}

ordered = sorted(
    nodes.keys(),
    key=lambda n: (TYPE_ORDER.get(nodes[n].get("type", "unknown"), 99), n),
)

cols = st.columns(3)
for i, name in enumerate(ordered):
    node = nodes[name]
    node_type = node.get("type", "unknown")
    color = TYPE_COLORS.get(node_type, "#4b5563")
    children = node.get("children") or []

    if children:
        children_html = "".join(
            f'<span style="background:#1f2937;color:#d1d5db;'
            f'padding:2px 8px;border-radius:4px;margin:2px 4px 2px 0;'
            f'font-family:monospace;font-size:11px;display:inline-block;">'
            f'{html.escape(c)}</span>'
            for c in children
        )
    else:
        children_html = (
            '<span style="color:#6b7280;font-style:italic;font-size:11px;">'
            "no downstream dependents</span>"
        )

    with cols[i % 3]:
        st.markdown(
            f"""
            <div style="background:#111827;border:1px solid #1f2937;
                        border-radius:10px;padding:14px 16px;margin-bottom:12px;
                        min-height:150px;">
              <div style="display:flex;align-items:center;gap:10px;
                          margin-bottom:8px;">
                <span style="font-size:10px;text-transform:uppercase;
                             letter-spacing:0.05em;color:#fff;
                             background:{color};padding:3px 9px;
                             border-radius:999px;font-weight:600;">
                  {html.escape(node_type)}
                </span>
                <span style="font-family:monospace;font-size:14px;
                             color:#f3f4f6;font-weight:600;">
                  {html.escape(name)}
                </span>
              </div>
              <div style="font-family:monospace;font-size:11px;
                          color:#6b7280;margin-bottom:10px;">
                {html.escape(node.get("terraform_address") or "")}<br>
                <span style="opacity:0.7">
                  {html.escape(node.get("source_file") or "")}
                </span>
              </div>
              <div style="font-size:12px;">
                <span style="color:#6b7280;text-transform:uppercase;
                             font-size:10px;letter-spacing:0.05em;">affects</span>
                &nbsp;{children_html}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with st.expander(f"Dependency edges ({len(edges)})"):
    if not edges:
        st.caption("No edges found.")
    else:
        for e in edges:
            st.markdown(f"`{e['from']}` → `{e['to']}`")

st.divider()
st.caption(
    "Owner, criticality, and customer_facing default to safe values. "
    "Terraform cannot infer them — edit the generated YAML to set them manually."
)