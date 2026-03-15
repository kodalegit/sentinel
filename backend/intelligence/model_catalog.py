from models import (
    LLMModelCatalogEntry,
    LLMModelCatalogResponse,
    LLMProviderCatalog,
)


def get_llm_model_catalog() -> LLMModelCatalogResponse:
    return LLMModelCatalogResponse(
        providers=[
            LLMProviderCatalog(
                value="openai",
                label="OpenAI",
                description="Managed OpenAI chat models for production and demo use.",
                requires_api_key=True,
                supports_base_url=True,
                supports_custom_model=True,
                models=[
                    LLMModelCatalogEntry(
                        value="gpt-5-mini",
                        label="GPT-5 Mini",
                        description="Best default for balanced quality, speed, and multimodal reasoning.",
                        recommended=True,
                    ),
                    LLMModelCatalogEntry(
                        value="gpt-5-nano",
                        label="GPT-5 Nano",
                        description="Lower-cost option for fast demos and lightweight tasks.",
                    ),
                    LLMModelCatalogEntry(
                        value="gpt-5.4",
                        label="GPT-5.4",
                        description="Latest OpenAI model with improved reasoning and context handling.",
                        deprecated=True,
                    ),
                    LLMModelCatalogEntry(
                        value="gpt-4.1",
                        label="GPT-4.1",
                        description="Legacy low-cost option for fallback scenarios.",
                        deprecated=True,
                    ),
                ],
            ),
            LLMProviderCatalog(
                value="anthropic",
                label="Anthropic",
                description="Claude models suited to structured reasoning and case analysis.",
                requires_api_key=True,
                supports_base_url=False,
                supports_custom_model=True,
                models=[
                    LLMModelCatalogEntry(
                        value="claude-sonnet-4-6",
                        label="Claude Sonnet 4.6",
                        description="Recommended Anthropic model for analysis quality and reliability.",
                        recommended=True,
                    ),
                    LLMModelCatalogEntry(
                        value="claude-haiku-4-5-20251001",
                        label="Claude Haiku 4.5",
                        description="Faster, lighter model for low-latency interactions.",
                    ),
                    LLMModelCatalogEntry(
                        value="claude-opus-4-6",
                        label="Claude Opus 4.6",
                        description="High-capability legacy option retained for compatibility.",
                        deprecated=True,
                    ),
                ],
            ),
            LLMProviderCatalog(
                value="google_genai",
                label="Google AI",
                description="Gemini models accessed through Google Generative AI.",
                requires_api_key=True,
                supports_base_url=False,
                supports_custom_model=True,
                models=[
                    LLMModelCatalogEntry(
                        value="gemini-2.5-flash",
                        label="Gemini 2.5 Flash",
                        description="Recommended default for speed-sensitive analysis and demos.",
                        recommended=True,
                    ),
                    LLMModelCatalogEntry(
                        value="gemini-3-flash-preview",
                        label="Gemini 3 Flash Preview",
                        description="Higher-context option for large evidence packs and longer prompts.",
                    ),
                    LLMModelCatalogEntry(
                        value="gemini-3.1-pro-preview",
                        label="Gemini 3.1 Pro Preview",
                        description="Higher-context option for large evidence packs and longer prompts.",
                    ),
                ],
            ),
            LLMProviderCatalog(
                value="ollama",
                label="Ollama (Local)",
                description="Local model serving for offline demos or private deployments.",
                requires_api_key=False,
                supports_base_url=True,
                supports_custom_model=True,
                models=[
                    LLMModelCatalogEntry(
                        value="llama3.1:8b",
                        label="Llama 3.1 8B",
                        description="Recommended local default for balanced quality and laptop-friendly performance.",
                        recommended=True,
                    ),
                    LLMModelCatalogEntry(
                        value="llama3.1:70b",
                        label="Llama 3.1 70B",
                        description="Higher-quality local option for powerful hardware.",
                    ),
                    LLMModelCatalogEntry(
                        value="mistral:7b",
                        label="Mistral 7B",
                        description="Lightweight local option for quick experimentation.",
                    ),
                ],
            ),
        ]
    )
