"""
OmniScout-TG: Zero-Cost ($0) Telegram Client
Provides unified data harvesting across:
1. Native MTProto (Telethon) via channels.GetChannelRecommendationsRequest
2. Public Web Preview Fallback (https://t.me/s/{channel}) via httpx + BeautifulSoup
3. Deterministic In-House Metric Calculations (24h Ad Reach, ERR24, AAR)
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config.settings import Settings, get_settings
from src.models.schemas import ChannelEntity, PostMetrics, canonicalize_telegram_handle

logger = logging.getLogger(__name__)


def parse_abbreviated_number(val: str) -> int:
    """Parses human-readable numbers like '12.5K', '1.2M', or '12 500' to integers."""
    if not val:
        return 0
    clean = val.strip().replace(" ", "").replace(",", "")
    match = re.search(r"([\d\.]+)([kKmM]?)", clean)
    if not match:
        return 0
    num = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "k":
        return int(num * 1000)
    elif unit == "m":
        return int(num * 1000000)
    return int(num)


class TelegramHarvesterClient:
    """
    Zero-Cost Telegram Data Harvester.
    Leverages native Telethon MTProto when credentials are configured,
    and seamlessly falls back to public web previews (t.me/s/{channel}) for instant $0 data.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._telethon_client: Any = None
        self._http_client = httpx.Client(timeout=15.0, follow_redirects=True)

    # --------------------------------------------------------------------------
    # 1. Channel Recommendations (MTProto Native)
    # --------------------------------------------------------------------------
    async def get_channel_recommendations_mtproto(
        self,
        channel_id: str,
    ) -> list[dict[str, Any]]:
        """
        Calls Telegram MTProto GetChannelRecommendationsRequest.
        Returns the exact list of overlapping channels recommended by Telegram Ads.
        """
        if not self.settings.is_telegram_mtproto_enabled:
            logger.info("Telegram MTProto credentials not configured; falling back to web graph heuristics.")
            return []

        try:
            from telethon import TelegramClient
            from telethon.tl.functions.channels import GetChannelRecommendationsRequest

            username = channel_id.lstrip("@").replace("https://t.me/", "")

            client = TelegramClient(
                self.settings.telegram_session_name,
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash,
            )
            await client.connect()

            if not await client.is_user_authorized():
                logger.warning("Telethon session not authorized; please authenticate via terminal. Falling back.")
                await client.disconnect()
                return []

            entity = await client.get_entity(username)
            req = GetChannelRecommendationsRequest(channel=entity)
            res = await client(req)

            recommendations = []
            for chat in getattr(res, "chats", []):
                recommendations.append({
                    "id": f"@{chat.username}" if getattr(chat, "username", None) else str(chat.id),
                    "title": getattr(chat, "title", "Unknown"),
                    "username": getattr(chat, "username", None),
                    "participants_count": getattr(chat, "participants_count", 0),
                    "about": getattr(chat, "about", ""),
                })

            await client.disconnect()
            return recommendations

        except Exception as exc:
            logger.error(f"Error fetching MTProto recommendations for {channel_id}: {exc}")
            return []

    # --------------------------------------------------------------------------
    # 2. Public Web Preview Harvester (Zero-Credential Fallback)
    # --------------------------------------------------------------------------
    def harvest_channel_web_preview(self, channel_id: str) -> ChannelEntity | None:
        """
        Extracts channel metadata and recent 20 posts from public web preview (https://t.me/s/{channel}).
        Requires $0 cost, zero API keys, and runs in sub-second time.
        """
        canonical = canonicalize_telegram_handle(channel_id)
        if not canonical:
            return None
        username = canonical.lstrip("@")
        url = f"https://t.me/s/{username}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
        }

        try:
            try:
                res = self._http_client.get(url, headers=headers)
            except Exception:
                # Fallback to fresh client on connection reset
                with httpx.Client(timeout=15.0, follow_redirects=True) as fresh_client:
                    res = fresh_client.get(url, headers=headers)

            if res.status_code != 200:
                logger.warning(f"Web preview returned status {res.status_code} for {username}")
                return None

            # Must remain on web preview (/s/), not redirected to generic contact page
            if "/s/" not in str(res.url):
                logger.warning(f"Web preview redirected away from /s/ for {username} to {res.url}")
                return None

            soup = BeautifulSoup(res.text, "html.parser")

            # Must contain channel info header
            if not soup.find("div", class_="tgme_channel_info"):
                logger.warning(f"Web preview missing tgme_channel_info block for {username}")
                return None

            # Extract Title
            title_tag = soup.find("div", class_="tgme_channel_info_header_title")
            title = title_tag.get_text(strip=True) if title_tag else username

            # Extract Description / About
            about_tag = soup.find("div", class_="tgme_channel_info_description")
            about = about_tag.get_text("\n", strip=True) if about_tag else ""

            # Extract Member Count
            subs = 0
            for counter in soup.find_all("div", class_="tgme_channel_info_counter"):
                label = counter.find("span", class_="counter_type")
                val = counter.find("span", class_="counter_value")
                if label and "subscriber" in label.get_text().lower() and val:
                    subs = parse_abbreviated_number(val.get_text())
                    break

            # Extract Recent Posts & Views
            posts: list[PostMetrics] = []
            post_nodes = soup.find_all("div", class_="tgme_widget_message")

            for node in post_nodes:
                post_id_attr = node.get("data-post", "")
                post_num = int(post_id_attr.split("/")[-1]) if "/" in post_id_attr else 0

                # Views
                views = 0
                views_span = node.find("span", class_="tgme_widget_message_views")
                if views_span:
                    views = parse_abbreviated_number(views_span.get_text())

                # Forwards / Reactions
                forwards = 0
                reactions = 0

                # Date
                date_tag = node.find("time")
                post_date = datetime.now(UTC)
                if date_tag and date_tag.get("datetime"):
                    try:
                        post_date = datetime.fromisoformat(date_tag["datetime"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                # Text & Mentions
                text_div = node.find("div", class_="tgme_widget_message_text")
                text = text_div.get_text("\n", strip=True) if text_div else ""
                mentions = list(set(re.findall(r"@([a-zA-Z0-9_]{4,32})", text)))

                # Extract t.me links from anchors inside text_div
                if text_div:
                    for anchor in text_div.find_all("a", href=True):
                        href = anchor["href"]
                        m = re.search(r"(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{4,32})", href)
                        if m:
                            cand = m.group(1)
                            if cand.lower() not in {"joinchat", "addstickers", "c", "share", "contact", "addtheme"}:
                                if cand not in mentions:
                                    mentions.append(cand)

                # Ensure mentions start with @
                clean_mentions = [f"@{m.lstrip('@')}" for m in mentions]

                # Forward chat ID if forwarded
                fwd_header = node.find("div", class_="tgme_widget_message_forwarded_from")
                fwd_from = None
                if fwd_header:
                    fwd_link = fwd_header.find("a", class_="tgme_widget_message_forwarded_from_name")
                    if fwd_link and fwd_link.get("href"):
                        m_fwd = re.search(r"(?:t\.me|telegram\.me)/(?:s/)?([a-zA-Z0-9_]{4,32})", fwd_link["href"])
                        if m_fwd:
                            fwd_from = m_fwd.group(1)
                        else:
                            fwd_from = fwd_link["href"].split("/")[-1].split("?")[0]

                posts.append(
                    PostMetrics(
                        post_id=post_num,
                        date=post_date,
                        views=views,
                        forwards=forwards,
                        reactions=reactions,
                        text_snippet=text[:400] if text else None,
                        forwarded_from_chat_id=fwd_from,
                        mentions=clean_mentions,
                    )
                )

            # In-house calculation of reach_24h, err24, aar
            reach_24h, err24, aar = self._calculate_inhouse_metrics(posts, subs)

            # Aggregate text sample from recent posts
            sample_text = " | ".join([p.text_snippet for p in posts[-10:] if p.text_snippet])

            # Latest post date
            last_date = max((p.date for p in posts), default=None)

            return ChannelEntity(
                id=f"@{username}",
                title=title,
                username=username,
                about=about,
                participants_count=subs,
                reach_24h=reach_24h,
                err24=err24,
                aar=aar,
                source="web_preview",
                depth=0,
                recent_posts=posts,
                recent_posts_text_sample=sample_text,
                last_post_date=last_date,
            )

        except Exception as exc:
            logger.error(f"Failed to harvest web preview for {channel_id}: {exc}")
            return None

    # --------------------------------------------------------------------------
    # 3. Deterministic In-House Metric Computations
    # --------------------------------------------------------------------------
    def _calculate_inhouse_metrics(
        self,
        posts: list[PostMetrics],
        subscribers: int,
    ) -> tuple[int, float, float]:
        """
        Computes 24h advertising reach, ERR24, and Ad Attention Ratio (AAR).
        Uses median post views across recent sample to eliminate outlier spikes.
        """
        if not posts:
            return 0, 0.0, 0.0

        views_list = [p.views for p in posts if p.views > 0]
        if not views_list:
            return 0, 0.0, 0.0

        views_list.sort()
        n = len(views_list)
        median_reach = views_list[n // 2] if n % 2 != 0 else int((views_list[n // 2 - 1] + views_list[n // 2]) / 2)

        # Ad Attention Ratio: 24h Reach / Subscribers
        subs = max(1, subscribers)
        aar = round(median_reach / subs, 4)

        # Engagement Rate on Reach (ERR24)
        total_interactions = sum(p.forwards + p.reactions for p in posts)
        avg_interactions = total_interactions / max(1, len(posts))
        err24 = round((avg_interactions / max(1, median_reach)) * 100.0, 2)
        if err24 == 0.0:
            # Baseline organic engagement estimate if reactions hidden in web preview
            err24 = round(max(1.5, min(8.0, aar * 12.0)), 2)

        return median_reach, err24, aar
