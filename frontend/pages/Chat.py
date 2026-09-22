import uuid
import html
import streamlit as st

def detect_lang(text):
    """Detect whether the text contains Arabic characters."""
    return "ar" if any('\u0600' <= c <= '\u06ff' for c in text) else "en"

from api_client import post_json_detailed, post_bytes, post_multipart
from style import apply_style, sidebar, empty_state

st.set_page_config(page_title="Spectre Chat", page_icon="💬", layout="wide")
apply_style()
sidebar("Chat")

st.title("💬 Lya — Spectre Impact Assistant")
st.caption("Ask about PR risk, blast radius, affected services, deployment validation, or rollback.")

st.info("🌐 Lya responds in Arabic 🇪🇬 or English 🇬🇧 based on your message.")

if "spectre_chat" not in st.session_state:
    st.session_state.spectre_chat = []
if "spectre_chat_session_id" not in st.session_state:
    st.session_state.spectre_chat_session_id = str(uuid.uuid4())
if "chat_pending" not in st.session_state:
    st.session_state.chat_pending = None

h1, h2, h3 = st.columns([3, 1, 1])
with h1:
    st.caption(f"Chat with Lya · {len(st.session_state.spectre_chat)} messages")
with h2:
    if st.button("🆕 New Chat", help="Start a new conversation.", use_container_width=True):
        session_id = st.session_state.spectre_chat_session_id

        # The backend contract may expose session_id as a query parameter.
        ok, data, status = post_json_detailed(
            f"/api/chat/clear?session_id={session_id}",
            {},
        )
        # Backward-compatible fallback for a backend that still accepts JSON.
        if not ok and status in (400, 422):
            ok, data, status = post_json_detailed(
                "/api/chat/clear",
                {"session_id": session_id},
            )

        st.session_state.spectre_chat = []
        st.session_state.spectre_chat_session_id = str(uuid.uuid4())

        if ok or status in (404, None):
            st.toast("New chat started")
        else:
            st.warning(
                data.get("message")
                or data.get("error")
                or "Could not reset backend memory."
            )
        st.rerun()

with h3:
    if st.session_state.spectre_chat:
        text = "\n\n".join(
            f"{m['role'].title()}: {m['content']}"
            for m in st.session_state.spectre_chat
        )
        st.download_button(
            "⬇️ Export",
            text,
            file_name="spectre_chat.txt",
            mime="text/plain",
            use_container_width=True,
            help="Download this conversation as a text file.",
        )

if not st.session_state.spectre_chat:
    st.markdown(
        empty_state(
            "🤖",
            "Hi, I'm Lya.",
            "Ask me about any file in your repo, and I'll tell you what could break.",
        ),
        unsafe_allow_html=True,
    )

# Render all persisted messages using the same bubble style.
for i, message in enumerate(st.session_state.spectre_chat):
    role = message["role"]
    css = "spectre-chat-user" if role == "user" else "spectre-chat-assistant"
    avatar = "👤" if role == "user" else "🤖"
    label = "You" if role == "user" else "Lya"

    safe_content = html.escape(str(message.get("content", ""))).replace("\n", "<br>")
    st.markdown(
        f"<div class='spectre-chat-bubble {css}'>"
        f"<div><b>{avatar} {label}</b></div>"
        f"<div>{safe_content}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if role == "assistant":
        tools = message.get("tool_calls") or message.get("tools") or []
        if tools:
            st.caption("🛠️ Tools used")
            for tool in tools:
                name = tool.get("name") if isinstance(tool, dict) else str(tool)
                safe_name = html.escape(str(name))
                st.markdown(
                    f"<div class='spectre-tool-call'>⚙️ {safe_name}</div>",
                    unsafe_allow_html=True,
                )

        if st.button(
            "🔊 Speak",
            key=f"speak_{i}",
            help="Play this message as audio.",
        ):
            ok, audio, mime = post_bytes(
                "/api/tts",
                {"text": message["content"], "language": "auto"},
                timeout=60,
            )
            if ok:
                st.session_state[f"chat_audio_{i}"] = (
                    audio,
                    mime if mime.startswith("audio/") else "audio/mpeg",
                )
            else:
                st.warning("TTS is not connected yet.")

        if st.session_state.get(f"chat_audio_{i}"):
            audio, mime = st.session_state[f"chat_audio_{i}"]
            st.audio(audio, format=mime)

st.markdown("### Suggested questions")
suggestions = [
    "What services are affected by customer_database.tf?",
    "Who owns the payment service?",
    "Show me past incidents",
    "What should I validate before deploy?",
]
cols = st.columns(2)
for i, question in enumerate(suggestions):
    if cols[i % 2].button(
        question,
        key=f"suggest_{i}",
        use_container_width=True,
        help="Send this question to Lya.",
    ):
        st.session_state.chat_pending = question
        st.rerun()

# Optional STT integration. If the backend does not expose /api/stt,
# the UI fails gracefully rather than crashing the page.
if hasattr(st, "audio_input"):
    st.markdown("### 🎙️ Voice Input")
    audio_input = st.audio_input("Record a question")
    if audio_input is not None:
        st.success("🎙️ Recording captured.")
        if st.button("Use Recording", key="use_recording", help="Transcribe the recording and send it to Lya."):
            ok, data, status = post_multipart(
                "/api/stt",
                {
                    "audio": (
                        audio_input.name,
                        audio_input.getvalue(),
                        audio_input.type or "audio/wav",
                    )
                },
                {"session_id": st.session_state.spectre_chat_session_id},
            )
            if ok:
                transcript = (
                    data.get("text")
                    or data.get("transcript")
                    or data.get("message")
                )
                if transcript:
                    st.session_state.chat_pending = transcript
                    st.rerun()
                else:
                    st.warning("STT returned no transcript.")
            elif status == 404:
                st.info("Voice transcription is not enabled by the current backend.")
            else:
                st.warning(
                    data.get("message")
                    or data.get("error")
                    or "STT API is not connected yet."
                )
else:
    st.caption("🎙️ Microphone input requires a recent Streamlit version.")

# Streamlit requires st.chat_input() to be present on every run.
pending = st.session_state.pop("chat_pending", None)
typed = st.chat_input("Ask Lya...", key="lya_chat_input")
prompt = typed or pending

if prompt:
    st.session_state.spectre_chat.append(
        {"role": "user", "content": prompt}
    )

    # Animated typing indicator while the request is in flight.
    typing = st.empty()
    typing.markdown(
        "<div class='spectre-typing'><span></span><span></span><span></span></div>",
        unsafe_allow_html=True,
    )

    try:
        ok, data, status = post_json_detailed(
            "/api/chat",
            {
                "message": prompt,
                "session_id": st.session_state.spectre_chat_session_id,
            },
            timeout=180,
        )
    finally:
        typing.empty()

    if ok:
        answer = (
            data.get("response")
            or data.get("answer")
            or data.get("message")
            or "No response returned."
        )
        tools = data.get("tool_calls") or data.get("tools") or []
        st.session_state.spectre_chat.append(
            {
                "role": "assistant",
                "content": answer,
                "tool_calls": tools,
            }
        )
    elif status == 400:
        msg = (
            data.get("message")
            or data.get("error")
            or "This input was blocked by the safety rules."
        )
        st.session_state.spectre_chat.append(
            {"role": "assistant", "content": f"🚫 {msg}"}
        )
    elif status == 500:
        msg = (
            data.get("message")
            or data.get("error")
            or "The AI service encountered a server error."
        )
        st.session_state.spectre_chat.append(
            {"role": "assistant", "content": f"⚠️ {msg}"}
        )
    else:
        msg = (
            data.get("error")
            or data.get("message")
            or "The Chat API is not connected yet."
        )
        st.session_state.spectre_chat.append(
            {"role": "assistant", "content": f"🔌 {msg}"}
        )

    st.rerun()
