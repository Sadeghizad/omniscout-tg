"""
OmniScout-TG: Strict Zero-Tolerance Live Channel Validator
Enforces 100% genuine live public validation for Telegram Ads eligibility:
1. Live HTTP probe on https://t.me/s/{username} (must return HTTP 200)
2. Valid non-empty channel title (reject placeholder/contact pages)
3. Hard Telegram Ads member threshold: members >= 1,000 (reject <1,000)
4. Activity threshold: Must have posts published within the last 14 days
5. Verified labeling: 'PUBLIC_WEB_VALIDATED' + caveat 'REQUIRES_MANUAL_CHECK_IN_ADS_PANEL'
"""

import logging
from datetime import UTC, datetime, timedelta

from config.settings import Settings, get_settings
from src.clients.telegram_client import TelegramHarvesterClient
from src.models.schemas import ChannelEntity, canonicalize_telegram_handle

logger = logging.getLogger(__name__)

# Minimum subscriber count required by official Telegram Ads platform
MIN_TELEGRAM_ADS_MEMBERS = 1000

# Maximum days since last post for an active channel
MAX_INACTIVE_DAYS = 14


class ChannelLiveValidator:
    """
    Zero-Tolerance Live Channel Validator for Telegram Ads campaigns.
    Never permits synthetic, unverified, inactive, or sub-1000 member channels.
    """

    def __init__(
        self,
        harvester: TelegramHarvesterClient | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.harvester = harvester or TelegramHarvesterClient(self.settings)

    def validate(
        self,
        channel_id: str,
        existing_entity: ChannelEntity | None = None,
    ) -> tuple[bool, ChannelEntity | None, str]:
        """
        Executes strict zero-tolerance validation against live Telegram preview.

        Returns:
            (is_valid, enriched_entity_or_none, reason_code)
        """
        clean_handle = canonicalize_telegram_handle(channel_id)
        if not clean_handle:
            return False, None, "REJECTED_INVALID_HANDLE"

        username = clean_handle.lstrip("@").strip()

        # Check for system/invalid handles
        if self._is_excluded_system_handle(clean_handle):
            return False, None, "REJECTED_SYSTEM_HANDLE"

        # Harvest or re-use harvested live preview
        entity = existing_entity
        if not entity or not entity.recent_posts:
            entity = self.harvester.harvest_channel_web_preview(username)

        # 1. HTTP Probe & Existence Check
        if not entity:
            logger.warning(f"Validator: Channel {clean_handle} failed HTTP probe or is private.")
            return False, None, "REJECTED_HTTP_ERROR"

        # 2. Title Verification
        title = (entity.title or "").strip()
        if not title or title.lower() in {username.lower(), "telegram: contact", "channel not found"}:
            entity.validation_status = "REJECTED_NO_TITLE"
            entity.is_verified_live = False
            return False, entity, "REJECTED_NO_TITLE"

        # 3. Telegram Ads Hard Member Threshold (>= 1,000 members)
        if entity.participants_count < MIN_TELEGRAM_ADS_MEMBERS:
            logger.info(
                f"Validator: Channel {clean_handle} has {entity.participants_count} members "
                f"(requires >= {MIN_TELEGRAM_ADS_MEMBERS}). Rejected."
            )
            entity.validation_status = "REJECTED_UNDER_1000_MEMBERS"
            entity.validation_caveat = f"Subscribers ({entity.participants_count:,}) < {MIN_TELEGRAM_ADS_MEMBERS} threshold"
            entity.is_verified_live = False
            return False, entity, "REJECTED_UNDER_1000_MEMBERS"

        # 4. Activity Check (Posts within last 14 days)
        if not entity.recent_posts:
            entity.validation_status = "REJECTED_NO_POSTS"
            entity.is_verified_live = False
            return False, entity, "REJECTED_NO_POSTS"

        now = datetime.now(UTC)
        cutoff_date = now - timedelta(days=MAX_INACTIVE_DAYS)

        # Determine last post date
        last_date = entity.last_post_date
        if not last_date and entity.recent_posts:
            last_date = max((p.date for p in entity.recent_posts if p.date), default=None)
            entity.last_post_date = last_date

        if not last_date:
            entity.validation_status = "REJECTED_NO_DATE"
            entity.validation_caveat = "Cannot verify recent post timestamps"
            entity.is_verified_live = False
            return False, entity, "REJECTED_NO_DATE"

        # Ensure timezone awareness for comparison
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=UTC)
        if last_date < cutoff_date:
            days_ago = (now - last_date).days
            logger.info(f"Validator: Channel {clean_handle} inactive ({days_ago} days since last post). Rejected.")
            entity.validation_status = "REJECTED_INACTIVE"
            entity.validation_caveat = f"Inactive: Last post was {days_ago} days ago (> {MAX_INACTIVE_DAYS}d limit)"
            entity.is_verified_live = False
            return False, entity, "REJECTED_INACTIVE"

        # 5. Passed all zero-tolerance checks!
        entity.validation_status = "PUBLIC_WEB_VALIDATED"
        entity.validation_caveat = "REQUIRES_MANUAL_CHECK_IN_ADS_PANEL"
        entity.is_verified_live = True

        logger.info(
            f"Validator: Channel {clean_handle} ({entity.title}) PASSED "
            f"({entity.participants_count:,} subs, {len(entity.recent_posts)} posts)."
        )
        return True, entity, "PUBLIC_WEB_VALIDATED"

    def _is_excluded_system_handle(self, handle: str) -> bool:
        excluded = {
            "@telegram", "@durov", "@botfather", "@ads", "@notcoin", "@fragment",
            "@telegramtips", "@sticker", "@themes", "@support", "@verify",
        }
        return handle.lower() in excluded
