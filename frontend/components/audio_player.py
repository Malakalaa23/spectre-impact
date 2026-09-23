import streamlit as st


def render_audio_player(
    audio_bytes: bytes,
    mime: str = "audio/mpeg",
    filename: str = "spectre_analysis.mp3",
) -> None:
    """Render the voice player inside a real Streamlit bordered container."""
    if not audio_bytes:
        st.info("No audio available yet.")
        return

    with st.container(border=True):
        st.caption("🎙️ Spectre Voice Analysis")
        st.audio(audio_bytes, format=mime)
        st.download_button(
            "⬇️ Download Audio",
            audio_bytes,
            file_name=filename,
            mime=mime,
            use_container_width=True,
            help="Download the generated voice analysis.",
        )
