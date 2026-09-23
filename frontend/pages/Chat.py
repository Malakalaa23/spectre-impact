"""
Chat.py — Lya chat page.

Layout:
    Header → message list → suggested questions → voice input → chat input.

Backend contracts (all in api_client.py):
    - POST /api/chat         — text message, timeout 180s
    - POST /api/chat/clear   — reset session, timeout 30s (session_id as query param)
    - POST /api/tts          — synthesize speech, timeout 60s
    - POST /api/stt          — transcribe audio, timeout 180s

Timeouts are explicit and generous. The first STT call after a fresh
container restart can pay the faster-whisper model load cost even with
startup warmup, so the client waits long enough for the server to finish
rather than giving up early with a misleading error.
"""

import uuid
import html
import streamlit as st

from api_client import post_json_detailed, post_bytes, post_multipart
from style import apply_style, sidebar, empty_state


# ---------------------------------------------------------------------------
# Page setup — st.set_page_config must be the first Streamlit call.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Lya — Spectre Impact Assistant",
    page_icon="💬",
    layout="wide",
)
apply_style()
sidebar("Chat")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "spectre_chat" not in st.session_state:
    st.session_state.spectre_chat = []

if "spectre_chat_session_id" not in st.session_state:
    st.session_state.spectre_chat_session_id = str(uuid.uuid4())

if "chat_pending" not in st.session_state:
    st.session_state.chat_pending = None


# ---------------------------------------------------------------------------
# Language helper
# ---------------------------------------------------------------------------
def _detect_lang(text: str) -> str:
    """Return 'ar' if the text contains Arabic characters, otherwise 'en'."""
    return "ar" if any("\u0600" <= c <= "\u06ff" for c in text) else "en"


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("💬 Lya — Spectre Impact Assistant")
st.caption(
    "Your bilingual DevOps copilot. Ask her about blast radius, business "
    "impact, past incidents, ownership, or rollback plans — in English or "
    "Egyptian Arabic."
)

st.info(
    "🌐 Lya answers in whatever language you write in. "
    "She cites evidence from real PRs and services, never guesses."
)

# Capability hint
st.markdown(
    "<div style='display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 20px 0;'>"
    "<span style='padding:4px 10px;border-radius:12px;background:#1e293b;color:#94a3b8;font-size:12px;'>Blast radius</span>"
    "<span style='padding:4px 10px;border-radius:12px;background:#1e293b;color:#94a3b8;font-size:12px;'>Business impact</span>"
    "<span style='padding:4px 10px;border-radius:12px;background:#1e293b;color:#94a3b8;font-size:12px;'>Past incidents</span>"
    "<span style='padding:4px 10px;border-radius:12px;background:#1e293b;color:#94a3b8;font-size:12px;'>Ownership</span>"
    "<span style='padding:4px 10px;border-radius:12px;background:#1e293b;color:#94a3b8;font-size:12px;'>Rollback</span>"
    "<span style='padding:4px 10px;border-radius:12px;background:#1e293b;color:#94a3b8;font-size:12px;'>Deployment validation</span>"
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Toolbar: message count, New Chat, Export
# ---------------------------------------------------------------------------
h1, h2, h3 = st.columns([3, 1, 1])

with h1:
    msg_count = len(st.session_state.spectre_chat)
    if msg_count == 0:
        st.caption("Chat with Lya · starting fresh")
    else:
        last_user = next(
            (m for m in reversed(st.session_state.spectre_chat) if m["role"] == "user"),
            None,
        )
        if last_user:
            lang = _detect_lang(last_user.get("content", ""))
            lang_label = "🇪🇬 Arabic" if lang == "ar" else "🇬🇧 English"
            st.caption(f"Chat with Lya · {msg_count} messages · replying in {lang_label}")
        else:
            st.caption(f"Chat with Lya · {msg_count} messages")

with h2:
    if st.button("🆕 New Chat", help="Start a new conversation.", use_container_width=True):
        session_id = st.session_state.spectre_chat_session_id

        ok, data, status = post_json_detailed(
            f"/api/chat/clear?session_id={session_id}",
            {},
        )
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


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------
if not st.session_state.spectre_chat:
    st.markdown(
        empty_state(
            "🤖",
            "Hi, I'm Lya.",
            (
                "Tell me which file or service you're changing, and I'll show "
                "you what could break, who owns it, and whether this matches "
                "a past incident. Try asking about customer_database.tf to see "
                "what I do."
            ),
        ),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Message list
# ---------------------------------------------------------------------------
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
                err = audio.decode("utf-8", errors="replace") if isinstance(audio, bytes) else str(audio)
                st.warning(f"TTS failed: {err[:200] or 'unknown error'}")

        if st.session_state.get(f"chat_audio_{i}"):
            audio, mime = st.session_state[f"chat_audio_{i}"]
            st.audio(audio, format=mime)


# ---------------------------------------------------------------------------
# Suggested questions
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Voice input
# ---------------------------------------------------------------------------
if hasattr(st, "audio_input"):
    st.markdown("### 🎙️ Voice Input")
    audio_input = st.audio_input("Record a question")
    if audio_input is not None:
        st.success("🎙️ Recording captured.")
        if st.button(
            "Use Recording",
            key="use_recording",
            help="Transcribe the recording and send it to Lya.",
        ):
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
                timeout=180,
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


# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
pending = st.session_state.pop("chat_pending", None)
typed = st.chat_input("Ask Lya...", key="lya_chat_input")
prompt = typed or pending

if prompt:
    st.session_state.spectre_chat.append({"role": "user", "content": prompt})

    # Typing indicator while the request is in flight.
    typing = st.empty()
    typing.markdown(
        "<div style='padding:12px 16px;color:#94a3b8;font-size:14px;"
        "display:flex;align-items:center;gap:10px;'>"
        "<span>🤖 <b style='color:#e2e8f0;'>Lya</b> is analyzing your request</span>"
        "<span class='spectre-typing'>"
        "<span></span><span></span><span></span>"
        "</span>"
        "</div>",
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
            {"role": "assistant", "content": answer, "tool_calls": tools}
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