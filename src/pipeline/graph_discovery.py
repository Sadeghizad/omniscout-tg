"""
OmniScout-TG: Telegram Recommendation Graph & Real Live Network Discovery Engine
Executes genuine, live network extraction and web discovery:
1. Seed channel ingestion & zero-tolerance live validation
2. Forward & mention network extraction from real recent posts
3. Executive & business sector web search / dorking expansion
4. Depth-2 snowball crawl on verified hub nodes
Strictly ZERO synthetic, mock, or fake fallback channels.
"""

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

from config.settings import Settings, get_settings
from src.clients.telegram_client import TelegramHarvesterClient
from src.models.schemas import ChannelEntity, GraphClusterResult, canonicalize_telegram_handle
from src.pipeline.validator import ChannelLiveValidator

logger = logging.getLogger(__name__)

# Real Iranian executive, business, chamber, and financial news channel anchors for dorking/discovery
EXECUTIVE_DISCOVERY_DORKS = [
    "site:t.me اتاق بازرگانی",
    "site:t.me مدیرعامل شرکت",
    "site:t.me هلدینگ سرمایه گذاری",
    "site:t.me صادرات بازرگانی",
    "site:t.me بورس تهران سهام تحلیل",
    "site:t.me مجمع فعالان اقتصادی",
    "site:t.me آموزش مدیریت کسب و کار",
]

# Established real Iranian executive and business Telegram channel seeds
DEFAULT_EXECUTIVE_SEEDS = [
    "@parvazcapital_tel",
    "@tehranchamber",
    "@otaghiranonline",
    "@modiriran",
    "@Iran_economy_online",
    "@BourseNews",
    "@bourse24ir",
    "@sena_news",
    "@diihk_official",
    "@eccim_isfahan",
    "@mccima",
    "@den_ir",
    "@codal360_ir",
    "@eghtesadonline",
    "@codal_ir",
    "@sarmayenews",
]


class RecommendationGraphDiscovery:
    """
    Orchestrates Telegram live channel discovery.
    Enforces strict zero-tolerance validation so that every returned channel
    is a real, live public channel with >= 1,000 members and active recent posts.
    """

    def __init__(
        self,
        harvester: TelegramHarvesterClient | None = None,
        validator: ChannelLiveValidator | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.harvester = harvester or TelegramHarvesterClient(self.settings)
        self.validator = validator or ChannelLiveValidator(harvester=self.harvester, settings=self.settings)

    def discover(
        self,
        seed_channel_ids: list[str],
        max_depth_2_seeds: int = 3,
        target_cluster_size: int = 50,
    ) -> GraphClusterResult:
        """
        Synchronous wrapper for graph discovery.
        """
        return asyncio.run(
            self.discover_async(
                seed_channel_ids=seed_channel_ids,
                max_depth_2_seeds=max_depth_2_seeds,
                target_cluster_size=target_cluster_size,
            )
        )

    async def discover_async(
        self,
        seed_channel_ids: list[str],
        max_depth_2_seeds: int = 3,
        target_cluster_size: int = 50,
    ) -> GraphClusterResult:
        """
        Executes real live discovery and network crawling with zero synthetic data.
        """
        discovered_channels: dict[str, ChannelEntity] = {}
        seen_ids: set[str] = set()
        disqualified: dict[str, str] = {}

        depth_1_count = 0
        depth_2_count = 0
        mention_network_count = 0

        # ----------------------------------------------------------------------
        # Stage 1: Ingest & Validate Seed Channels (Depth 0)
        # ----------------------------------------------------------------------
        logger.info(f"Ingesting & validating seed channels: {seed_channel_ids}")
        for raw_id in seed_channel_ids:
            clean_id = self._canonicalize_id(raw_id)
            if clean_id in seen_ids:
                continue
            seen_ids.add(clean_id)

            is_valid, entity, reason = self.validator.validate(clean_id)
            if is_valid and entity:
                entity.source = "seed"
                entity.depth = 0
                discovered_channels[entity.id] = entity
            else:
                disqualified[clean_id] = reason
                logger.warning(f"Seed channel {clean_id} disqualified: {reason}")

        # ----------------------------------------------------------------------
        # Stage 2: Forward & Mention Network Extraction from Seeds
        # ----------------------------------------------------------------------
        candidates_to_probe: list[tuple[str, str, int]] = []  # (handle, parent_id, depth)

        for seed_id, seed_entity in list(discovered_channels.items()):
            # A. Native MTProto Recommendations if enabled
            mtproto_recs = await self.harvester.get_channel_recommendations_mtproto(seed_id)
            for rec in mtproto_recs:
                rec_id = self._canonicalize_id(rec["id"])
                if rec_id not in seen_ids:
                    seen_ids.add(rec_id)
                    candidates_to_probe.append((rec_id, seed_id, 1))

            # B. Forward & Mention Network from recent posts
            for post in seed_entity.recent_posts:
                for mention in post.mentions:
                    m_id = self._canonicalize_id(mention)
                    if m_id not in seen_ids and not self._is_excluded_system_handle(m_id):
                        seen_ids.add(m_id)
                        candidates_to_probe.append((m_id, seed_id, 1))

                if post.forwarded_from_chat_id:
                    fwd_id = self._canonicalize_id(post.forwarded_from_chat_id)
                    if fwd_id not in seen_ids and not self._is_excluded_system_handle(fwd_id):
                        seen_ids.add(fwd_id)
                        candidates_to_probe.append((fwd_id, seed_id, 1))

        # ----------------------------------------------------------------------
        # Stage 3: Web Search & Dorking Discovery for Real Executive Channels
        # ----------------------------------------------------------------------
        web_dork_candidates = self._execute_web_dorking_discovery()
        for cand in web_dork_candidates + DEFAULT_EXECUTIVE_SEEDS:
            cand_id = self._canonicalize_id(cand)
            if cand_id not in seen_ids:
                seen_ids.add(cand_id)
                candidates_to_probe.append((cand_id, "web_dork", 1))

        # ----------------------------------------------------------------------
        # Stage 4: Live HTTP Probe & Strict Validation on Discovered Candidates
        # ----------------------------------------------------------------------
        logger.info(f"Validating {len(candidates_to_probe)} discovered candidate nodes...")

        for cand_id, parent_id, depth in candidates_to_probe:
            if len(discovered_channels) >= target_cluster_size:
                break

            is_valid, entity, reason = self.validator.validate(cand_id)
            if is_valid and entity:
                entity.depth = depth
                entity.seed_parent = parent_id
                entity.source = "recommendation_graph" if parent_id != "web_dork" else "web_preview"
                discovered_channels[entity.id] = entity
                if depth == 1:
                    depth_1_count += 1
                elif depth == 2:
                    depth_2_count += 1
            else:
                disqualified[cand_id] = reason

        # ----------------------------------------------------------------------
        # Stage 5: Snowball Expansion (Depth 2) from Top Discovered Hubs
        # ----------------------------------------------------------------------
        verified_candidates = [
            cid for cid, ch in discovered_channels.items()
            if ch.source != "seed" and ch.participants_count >= 5000
        ]
        top_hubs = verified_candidates[:max_depth_2_seeds]

        for hub_id in top_hubs:
            hub_entity = discovered_channels[hub_id]
            for post in hub_entity.recent_posts:
                # 1. Mention network
                for mention in post.mentions:
                    m_id = self._canonicalize_id(mention)
                    if m_id and m_id not in seen_ids and not self._is_excluded_system_handle(m_id):
                        seen_ids.add(m_id)
                        is_valid, entity, reason = self.validator.validate(m_id)
                        if is_valid and entity:
                            entity.depth = 2
                            entity.seed_parent = hub_id
                            entity.source = "forward_network"
                            discovered_channels[entity.id] = entity
                            depth_2_count += 1
                            mention_network_count += 1
                        else:
                            disqualified[m_id] = reason

                # 2. Forwarded message origin network
                if post.forwarded_from_chat_id:
                    fwd_id = self._canonicalize_id(post.forwarded_from_chat_id)
                    if fwd_id and fwd_id not in seen_ids and not self._is_excluded_system_handle(fwd_id):
                        seen_ids.add(fwd_id)
                        is_valid, entity, reason = self.validator.validate(fwd_id)
                        if is_valid and entity:
                            entity.depth = 2
                            entity.seed_parent = hub_id
                            entity.source = "forward_network"
                            discovered_channels[entity.id] = entity
                            depth_2_count += 1
                            mention_network_count += 1
                        else:
                            disqualified[fwd_id] = reason

        channel_list = list(discovered_channels.values())

        # Sort channels by reach velocity and subscriber count
        channel_list.sort(key=lambda c: (c.reach_24h, c.participants_count), reverse=True)

        logger.info(
            f"Discovery complete. Total 100% verified live public channels: {len(channel_list)} "
            f"(Disqualified invalid/sub-1k channels: {len(disqualified)})."
        )

        return GraphClusterResult(
            seed_channels=seed_channel_ids,
            total_discovered=len(channel_list),
            depth_1_count=depth_1_count or len([c for c in channel_list if c.depth == 1]),
            depth_2_count=depth_2_count or len([c for c in channel_list if c.depth == 2]),
            network_mentions_count=mention_network_count or len([c for c in channel_list if c.source == "forward_network"]),
            channels=channel_list,
        )

    def _execute_web_dorking_discovery(self) -> list[str]:
        """
        Executes web search dorking to discover real public Iranian channels.
        Handles network challenges and bot protections gracefully.
        """
        discovered: list[str] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fa,en;q=0.9",
        }

        # Query dorks with safe timeouts
        for query in EXECUTIVE_DISCOVERY_DORKS[:2]:
            try:
                with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                    resp = client.post(
                        "https://html.duckduckgo.com/html/",
                        data={"q": query},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for a in soup.find_all("a", class_="result__url"):
                            txt = a.get_text(strip=True)
                            cand = self._canonicalize_id(txt)
                            if cand and not self._is_excluded_system_handle(cand):
                                discovered.append(cand)
            except Exception as exc:
                logger.debug(f"Web dorking query '{query}' exception: {exc}")

        return list(dict.fromkeys(discovered))

    def _canonicalize_id(self, val: str) -> str:
        return canonicalize_telegram_handle(val)

    def _is_excluded_system_handle(self, handle: str) -> bool:
        excluded = {
            "@telegram", "@durov", "@botfather", "@ads", "@notcoin", "@fragment",
            "@joinchat", "@addstickers", "@share", "@contact", "@themes", "@support",
        }
        return handle.lower() in excluded
