import logging
from uuid import uuid4

from telegram import Update, InlineQueryResultAudio, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes

from ..utils.soundcloud_service import SoundcloudService

logger = logging.getLogger(__name__)


class InlineHandlers:
    def __init__(self, settings_manager, localization, soundcloud_service: SoundcloudService):
        self.settings_manager = settings_manager
        self.localization = localization
        self.soundcloud_service = soundcloud_service

    async def handle_inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline SoundCloud search."""
        query = (update.inline_query.query or "").strip()

        if not query:
            return

        results = []

        try:
            tracks = await self.soundcloud_service.search_tracks(query, limit=4)
            logger.info(f"Inline query '{query}' -> {len(tracks)} tracks")
        except Exception as e:
            logger.error(f"SoundCloud search failed: {e}", exc_info=True)
            tracks = []

        for track in tracks:
            try:
                stream_url = await self.soundcloud_service.get_stream_url(track)
                if not stream_url:
                    continue

                title = track.get("title") or "SoundCloud Track"
                user_info = track.get("user") or {}
                artist = user_info.get("username") or user_info.get("full_name") or ""

                display_title = f"{artist} - {title}" if artist else title
                duration = track.get("duration") or track.get("full_duration") or None
                duration_secs = int(duration / 1000) if duration else None

                caption_lines = [display_title]
                if permalink := track.get("permalink_url"):
                    caption_lines.append(permalink)

                results.append(
                    InlineQueryResultAudio(
                        id=str(uuid4()),
                        audio_url=stream_url,
                        title=display_title,
                        performer=artist or None,
                        audio_duration=duration_secs,
                        caption="\n".join(caption_lines),
                    )
                )
            except Exception as e:
                logger.error(f"Failed to build inline result: {e}", exc_info=True)
                continue

        if not results:
            # Fallback: allow sending the raw query back to the bot for standard handling
            fallback_text = query if query else "SoundCloud search failed"
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="SoundCloud поиск недоступен",
                    description="Нажми, чтобы отправить запрос боту",
                    input_message_content=InputTextMessageContent(
                        message_text=fallback_text
                    ),
                )
            )

        try:
            logger.info(f"Inline answer for '{query}' with {len(results)} results")
            await update.inline_query.answer(results, cache_time=0, is_personal=True)
        except Exception as e:
            logger.error(f"Failed to answer inline query: {e}", exc_info=True)
