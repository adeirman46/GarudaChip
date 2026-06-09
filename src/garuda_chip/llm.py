"""
Central LLM / embeddings factory for GarudaChip.

Everything in the app gets its chat model and embeddings from here, so the
provider can be switched with a single environment variable instead of editing
code. The DEFAULT is a fully-local setup: Ollama for chat (e.g. qwen3.5:9b) and
local sentence-transformers for embeddings.

Configure via .env (see .env.example):

    LLM_PROVIDER        ollama | google          (default: ollama)
    OLLAMA_MODEL        e.g. qwen3.5:9b
    OLLAMA_BASE_URL     default http://localhost:11434
    GOOGLE_API_KEY      required when LLM_PROVIDER=google
    GOOGLE_MODEL        default gemini-2.5-pro

    EMBEDDINGS_PROVIDER huggingface | ollama | google   (default: huggingface)
    EMBEDDING_MODEL     default all-MiniLM-L6-v2
"""

from __future__ import annotations

import os
import functools

from dotenv import load_dotenv

# Load .env from the nearest parent directory so it works no matter which
# tool sub-directory Streamlit is launched from.
load_dotenv()


def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


def provider_label() -> str:
    """Human-readable label for the active chat model (for the UI)."""
    provider = get_provider()
    if provider == "ollama":
        return f"Ollama · {os.getenv('OLLAMA_MODEL', 'qwen3.5:9b')} (local)"
    if provider in ("google", "gemini"):
        return f"Google · {os.getenv('GOOGLE_MODEL', 'gemini-2.5-pro')}"
    return provider


def get_chat_model(temperature: float = 0.2, **kwargs):
    """
    Return a LangChain chat model for the configured provider.

    Args:
        temperature: sampling temperature.
        **kwargs: forwarded to the underlying ChatModel constructor.
    """
    provider = get_provider()

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        timeout = os.getenv("OLLAMA_TIMEOUT")
        extra = {}
        if timeout:
            # langchain-ollama forwards client kwargs; a generous timeout keeps
            # long RTL generations from being cut off.
            try:
                extra["client_kwargs"] = {"timeout": float(timeout)}
            except ValueError:
                pass
        # qwen3 is a "thinking" model: by default it streams a long internal
        # reasoning pass BEFORE any answer tokens, which on slow/offloaded hardware
        # looks like "no output" and wastes time. Default thinking OFF for speed;
        # set OLLAMA_THINK=1 to watch the model reason.
        think = os.getenv("OLLAMA_THINK", "0").strip().lower() in ("1", "true", "yes", "on")
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
            reasoning=think,
            # --- Anti-repetition / runaway-generation guards ---
            # Small local models (esp. qwen) fall into degenerate loops where they
            # emit the SAME line(s) forever (e.g. "// We will assume … // But the
            # prompt says …"). A repeat penalty discourages the cycle, and a hard
            # num_predict cap guarantees generation STOPS even if a loop slips
            # through (otherwise it streams until OLLAMA_TIMEOUT). Tunable via .env.
            repeat_penalty=float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.18")),
            repeat_last_n=int(os.getenv("OLLAMA_REPEAT_LAST_N", "256")),
            num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "8192")),
            # Ollama caps the context at 2048 tokens by DEFAULT regardless of the
            # model's real window (qwen3.5 supports up to ~1M). That truncates the
            # RAG prompt and makes the model return NOTHING — the empty-output bug.
            # Raise it via OLLAMA_NUM_CTX. The KV cache costs ~56 KB/token for this
            # 9B model, so num_ctx is bounded by RAM/VRAM, not the model: 128k≈7 GB
            # and 256k≈15 GB of KV cache. On a 14 GB-RAM / 8 GB-VRAM box, 16k is the
            # sweet spot (holds the references with room to spare). A bigger window
            # does NOT improve output — it only needs to fit the prompt (~5-8k here).
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "32768")),
            **extra,
            **kwargs,
        )

    if provider in ("google", "gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=google but GOOGLE_API_KEY is not set. "
                "Add it to your .env file or switch LLM_PROVIDER=ollama."
            )
        return ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-pro"),
            google_api_key=api_key,
            temperature=temperature,
            **kwargs,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. Use 'ollama' or 'google'."
    )


@functools.lru_cache(maxsize=1)
def get_embeddings():
    """
    Return a LangChain embeddings object for the configured provider.

    Cached because loading a sentence-transformers model is expensive.

    NOTE: the prebuilt FAISS indexes in data/verilog_datasets were created with
    all-MiniLM-L6-v2 (384-dim). Keep EMBEDDINGS_PROVIDER=huggingface unless you
    rebuild those indexes, otherwise dimensions will not match.
    """
    provider = os.getenv("EMBEDDINGS_PROVIDER", "huggingface").strip().lower()

    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
        return HuggingFaceEmbeddings(
            model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            model_kwargs={"device": device},
        )

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    if provider in ("google", "gemini"):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    raise ValueError(
        f"Unknown EMBEDDINGS_PROVIDER={provider!r}. "
        "Use 'huggingface', 'ollama', or 'google'."
    )
