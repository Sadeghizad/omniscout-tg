"""
OmniScout-TG: b.ai Unified AI Gateway Client
Provides robust interfaces for:
1. Jev Decision Engine (POST /v1/decisions) with model "jev-latest" (choice, noul, score)
2. DeepSeek Chat Completions (POST /v1/chat/completions) with model "deepseek-v4.1-flash"
Includes retry policies, typed parsing, and offline mock support.
"""

import json
import logging
import time
from typing import Any

import httpx

from config.settings import Settings, get_settings
from src.models.schemas import ChannelEntity, JevTriageDecision

logger = logging.getLogger(__name__)


class BaiClientError(Exception):
    """Base exception for b.ai Gateway operations."""
    pass


class BaiAuthenticationError(BaiClientError):
    """Raised when API key is missing or invalid (HTTP 401/403)."""
    pass


class BaiRateLimitError(BaiClientError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    pass


class BaiClient:
    """Production client for b.ai Unified Gateway."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.b_ai_base_url.rstrip("/")
        self.api_key = self.settings.b_ai_api_key
        self.timeout = self.settings.b_ai_timeout_seconds
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    # --------------------------------------------------------------------------
    # 1. Jev Fast Decision Engine (POST /v1/decisions)
    # --------------------------------------------------------------------------
    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Submits a state and question battery to the Jev decision engine.
        Contract: POST https://api.b.ai/v1/decisions
        Supported question types: 'noul' (boolean probability), 'choice' (categorical), 'score' (ordinal).
        """
        payload = {
            "model": model or self.settings.b_ai_jev_model,
            "state": state,
            "questions": questions,
        }

        # If offline or running in mock mode without API key, return deterministic mock decision
        if not self.settings.is_bai_live_enabled:
            return self._mock_jev_decision(state, questions)

        url = f"{self.base_url}/decisions"
        return self._post_with_retry(url, payload)

    def triage_channel(
        self,
        channel: ChannelEntity,
        target_persona: str,
        category_criteria: dict[str, str | None] | None = None,
    ) -> JevTriageDecision:
        """
        Executes fast System 1 triage on a Telegram candidate channel using jev-latest.
        Evaluates brand_safety (noul), category (choice), and icp_alignment (score).
        """
        default_categories = category_criteria or {
            "tech_programming": "Software, Programming and IT",
            "business_marketing": "Business, Sales and Marketing",
            "finance_investing": "Finance, Markets, Capital and Trading",
            "crypto_web3": "Cryptocurrency and Blockchain",
            "general_news": "General News and Politics",
            "entertainment": "Entertainment, Memes and Lifestyle",
            "other": None,
        }

        state = {
            "channel_title": channel.title,
            "channel_about": channel.about or "بدون توضیحات",
            "recent_posts_sample": channel.recent_posts_text_sample[:1200] if channel.recent_posts_text_sample else channel.title,
            "subscribers": channel.participants_count,
            "target_persona": target_persona,
        }

        questions = {
            "brand_safety": {
                "type": "noul",
                "instructions": "Is this channel clean and free from betting, gambling, warez, crypto pumps, adult content, or scam advertisements?",
            },
            "category": {
                "type": "choice",
                "instructions": "Select the primary commercial and thematic category of this channel.",
                "criteria": default_categories,
            },
            "icp_alignment": {
                "type": "score",
                "instructions": "Evaluate how well the channel audience and editorial focus align with the target customer persona.",
                "criteria": [
                    "Irrelevant",
                    "Low Relevance",
                    "Moderate Relevance",
                    "High Relevance",
                    "Direct Match",
                ],
            },
        }

        raw = self.decide(state=state, questions=questions, model=self.settings.b_ai_jev_model)
        return self._parse_jev_triage_response(channel.id, raw)

    # --------------------------------------------------------------------------
    # 2. DeepSeek Chat Completions (POST /v1/chat/completions)
    # --------------------------------------------------------------------------
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        """
        Generates completions via OpenAI-compatible endpoint using deepseek-v4.1-flash.
        Contract: POST https://api.b.ai/v1/chat/completions
        """
        payload = {
            "model": model or self.settings.b_ai_deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if not self.settings.is_bai_live_enabled:
            return self._mock_deepseek_completion(messages)

        url = f"{self.base_url}/chat/completions"
        res = self._post_with_retry(url, payload)

        try:
            return res["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise BaiClientError(f"Unexpected chat completions response format: {res}") from exc

    def generate_creative_hook_and_rationale(
        self,
        channel: ChannelEntity,
        campaign_name: str,
        target_persona: str,
    ) -> dict[str, str]:
        """
        Generates bilingual selection rationales and tailored advertising angles for shortlisted channels.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a master Telegram media planner. For the shortlisted channel, produce:\n"
                    "1. RATIONALE_FA: Exactly 2 sentences in fluent Persian explaining why this channel's audience matches the product.\n"
                    "2. RATIONALE_EN: 2 sentences in English explaining the strategic placement value.\n"
                    "3. RECOMMENDED_FORMAT: The optimal ad format (e.g., 24h Post with Notification, Native Sponsored Review, Forwarded Post).\n"
                    "4. CREATIVE_ANGLE: The single best hook or creative angle to maximize conversions.\n"
                    "Output valid JSON format with keys: rationale_fa, rationale_en, recommended_format, creative_angle."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Campaign: {campaign_name}\n"
                    f"Target Persona: {target_persona}\n"
                    f"Channel: {channel.title} ({channel.id})\n"
                    f"Subscribers: {channel.participants_count:,}\n"
                    f"Bio: {channel.about}\n"
                    f"Sample Content: {channel.recent_posts_text_sample[:400]}"
                ),
            },
        ]

        text = self.chat_completion(messages=messages, temperature=0.3)
        try:
            # Parse JSON block if markdown fences were used
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            return json.loads(cleaned)
        except Exception:
            return {
                "rationale_fa": f"کانال {channel.title} به دلیل تناسب بالا با پرسونای هدف و مخاطبان متمرکز برای تبلیغ انتخاب شده است.",
                "rationale_en": f"Channel {channel.title} was shortlisted due to strong audience resonance with the campaign ICP.",
                "recommended_format": "24h Pinned Post + Notification",
                "creative_angle": "Direct problem-solution hook focusing on practical user benefits.",
            }

    # --------------------------------------------------------------------------
    # Internal HTTP & Retry Policy
    # --------------------------------------------------------------------------
    def _post_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Performs HTTP POST with exponential backoff on transient errors."""
        max_attempts = self.settings.b_ai_max_retries
        backoff = self.settings.b_ai_retry_backoff

        last_exception = None
        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=self.headers)

                    if response.status_code in (401, 403):
                        raise BaiAuthenticationError(f"b.ai Authentication failed ({response.status_code}): {response.text}")

                    if response.status_code == 429:
                        wait_sec = backoff * (2 ** (attempt - 1))
                        logger.warning(f"b.ai rate limit encountered. Retrying in {wait_sec:.1f}s...")
                        time.sleep(wait_sec)
                        continue

                    response.raise_for_status()
                    return response.json()

            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
                last_exception = exc
                if attempt == max_attempts:
                    break
                wait_sec = backoff * (2 ** (attempt - 1))
                logger.warning(f"b.ai connection error on attempt {attempt}/{max_attempts}. Retrying in {wait_sec:.1f}s: {exc}")
                time.sleep(wait_sec)

        raise BaiClientError(f"b.ai request to {url} failed after {max_attempts} attempts: {last_exception}")

    # --------------------------------------------------------------------------
    # Mock Deciders for Offline & CI Testing
    # --------------------------------------------------------------------------
    def _mock_jev_decision(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        """Returns realistic mock decision for testing without live API keys."""
        title = state.get("channel_title", "").lower()
        about = state.get("channel_about", "").lower()

        # Simple keyword heuristic for mock testing
        is_spam = any(w in title or w in about for w in ["bet", "casino", "poker", "قمار", "شرط‌بندی"])
        category = "finance_investing" if any(w in title or w in about for w in ["finance", "capital", "بورسی", "سرمایه", "ارز"]) else "tech_programming"
        score_val = 1 if is_spam else (5 if "capital" in title or "سرمایه" in title else 4)

        return {
            "model": "jev-latest",
            "decisions": {
                "brand_safety": {
                    "answer": not is_spam,
                    "confidence": 0.98 if not is_spam else 0.99,
                    "probabilities": {"true": 0.02 if is_spam else 0.98, "false": 0.98 if is_spam else 0.02},
                },
                "category": {
                    "choice": category,
                    "confidence": 0.92,
                },
                "icp_alignment": {
                    "score": score_val,
                    "label": "Direct Match" if score_val == 5 else ("High Relevance" if score_val == 4 else "Irrelevant"),
                    "confidence": 0.88,
                },
            },
        }

    def _mock_deepseek_completion(self, messages: list[dict[str, str]]) -> str:
        """Returns realistic mock completion for testing."""
        mock_obj = {
            "rationale_fa": "این کانال به دلیل حضور جامعه فعال سرمایه‌گذاران و تعامل بسیار بالا، بستر ایده‌آلی برای جذب لید باکیفیت است.",
            "rationale_en": "This channel was shortlisted due to its highly concentrated professional investor audience and strong 24h view velocity.",
            "recommended_format": "24h Pinned Post + Notification",
            "creative_angle": "Practical case-study format highlighting verifiable ROI and proven capital growth.",
        }
        return json.dumps(mock_obj, ensure_ascii=False)

    def _parse_jev_triage_response(self, channel_id: str, raw: dict[str, Any]) -> JevTriageDecision:
        """Parses b.ai raw decision response into typed JevTriageDecision."""
        decisions = raw.get("decisions", raw)

        # 1. Brand safety (noul)
        bs_info = decisions.get("brand_safety", {})
        if isinstance(bs_info, dict):
            brand_safe = bool(bs_info.get("answer", True))
            bs_conf = float(bs_info.get("confidence", 1.0))
        else:
            brand_safe = bool(bs_info)
            bs_conf = 1.0

        # 2. Category (choice)
        cat_info = decisions.get("category", {})
        if isinstance(cat_info, dict):
            category = str(cat_info.get("choice", cat_info.get("category", "other")))
            cat_conf = float(cat_info.get("confidence", 1.0))
        else:
            category = str(cat_info)
            cat_conf = 1.0

        # 3. ICP alignment (score)
        icp_info = decisions.get("icp_alignment", {})
        if isinstance(icp_info, dict):
            score = int(icp_info.get("score", 3))
            label = str(icp_info.get("label", "Moderate Relevance"))
            icp_conf = float(icp_info.get("confidence", 1.0))
        else:
            score = int(icp_info) if str(icp_info).isdigit() else 3
            label = "Relevance"
            icp_conf = 1.0

        passed = brand_safe and (score >= 3)

        return JevTriageDecision(
            channel_id=channel_id,
            brand_safe=brand_safe,
            brand_safety_confidence=bs_conf,
            category=category,
            category_confidence=cat_conf,
            icp_score=score,
            icp_score_label=label,
            icp_confidence=icp_conf,
            passed_triage=passed,
            raw_response=raw,
        )
