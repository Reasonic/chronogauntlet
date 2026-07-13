"""Candidate model roster for the M0 pilot.

The pilot needs 2 frontier + 2 mid/small open-weight models (PLANS §5). The exact
roster is finalized once we know which API keys are present; `available()` filters
to models whose key env var is set. Prices are USD per 1M tokens (input, output),
APPROXIMATE — used only to pre-estimate spend and calibrate §10; the pilot's real
token counts are the ground truth. Model IDs may need adjustment to match the
accounts actually in use.
"""
from __future__ import annotations

from typing import List

from .llm import ModelSpec

# M3 campaign roster (8 models, 5 vendors, full capability ladder). All IDs
# verified against each provider's /models on 2026-07-10 / re-confirmed 2026-07-11
# (Anthropic: opus-4-8, sonnet-5, haiku-4-5; DeepSeek: v4-flash, v4-pro). Prices
# are USD/1M tokens (in, out), APPROXIMATE — used only to pre-estimate spend; the
# campaign's real token counts are the ground truth.
ROSTER: List[ModelSpec] = [
    # --- Anthropic frontier lineup (opus > sonnet > haiku: within-vendor gradient) ---
    ModelSpec("claude-opus-4-8", "anthropic", "claude-opus-4-8", "frontier",
              "ANTHROPIC_API_KEY", price_in=15.0, price_out=75.0),
    ModelSpec("claude-sonnet-5", "anthropic", "claude-sonnet-5", "frontier",
              "ANTHROPIC_API_KEY", price_in=3.0, price_out=15.0),
    ModelSpec("claude-haiku-4-5", "anthropic", "claude-haiku-4-5-20251001", "frontier",
              "ANTHROPIC_API_KEY", price_in=1.0, price_out=5.0),
    # --- OpenAI frontier ---
    ModelSpec("gpt-5.5", "openai_compat", "gpt-5.5", "frontier",
              "OPENAI_API_KEY", base_url="https://api.openai.com/v1",
              base_url_env="OPENAI_BASE_URL", price_in=1.25, price_out=10.0),
    # --- DeepSeek V4 (pro > flash) mid open-weight ---
    ModelSpec("deepseek-v4-pro", "openai_compat", "deepseek-v4-pro", "open",
              "DEEPSEEK_API_KEY", base_url="https://api.deepseek.com",
              base_url_env="DEEPSEEK_BASE_URL", price_in=0.55, price_out=2.19),
    ModelSpec("deepseek-v4-flash", "openai_compat", "deepseek-v4-flash", "open",
              "DEEPSEEK_API_KEY", base_url="https://api.deepseek.com",
              base_url_env="DEEPSEEK_BASE_URL", price_in=0.27, price_out=1.10),
    # --- open-weight via Together (Meta, Alibaba); ids are provider-specific.
    # Qwen3.5 is hybrid-thinking; disable thinking so it emits the answer (with
    # thinking on it burned the entire token budget on reasoning). ---
    ModelSpec("llama-3.3-70b", "openai_compat",
              "meta-llama/Llama-3.3-70B-Instruct-Turbo", "open",
              "TOGETHER_API_KEY", base_url="https://api.together.xyz/v1",
              base_url_env="TOGETHER_BASE_URL", price_in=0.88, price_out=0.88),
    ModelSpec("qwen3.5-9b", "openai_compat", "Qwen/Qwen3.5-9B", "open",
              "TOGETHER_API_KEY", base_url="https://api.together.xyz/v1",
              base_url_env="TOGETHER_BASE_URL", price_in=0.30, price_out=0.30,
              extra_body={"chat_template_kwargs": {"enable_thinking": False}}),
]

BY_NAME = {m.name: m for m in ROSTER}


def available(roster: List[ModelSpec] = ROSTER) -> List[ModelSpec]:
    """Roster members whose API key env var is set."""
    return [m for m in roster if m.available()]
