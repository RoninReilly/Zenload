import logging
from typing import Optional, Tuple
from telegram import Update
from telegram.ext import ContextTypes
from ..downloaders import DownloaderFactory

logger = logging.getLogger(__name__)

class CallbackHandlers:
    def __init__(self, keyboard_builder, settings_manager, download_manager, localization, activity_logger=None):
        self.keyboard_builder = keyboard_builder
        self.settings_manager = settings_manager
        self.download_manager = download_manager
        self.localization = localization
        self.activity_logger = activity_logger

    async def _is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
        """Check if user is an admin in the specified chat"""
        if chat_id < 0:  # Group chat
            user_id = update.effective_user.id
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)
                return member.status in ['creator', 'administrator']
            except Exception as e:
                logger.error(f"Failed to check admin status: {e}")
                return False
        return True  # In private chats, user is always "admin"

    def get_message(self, user_id: int, key: str, chat_id: Optional[int] = None, is_admin: bool = False, **kwargs) -> str:
        """Get localized message"""
        settings = self.settings_manager.get_settings(user_id, chat_id, is_admin)
        language = settings.language
        return self.localization.get(language, key, **kwargs)

    def parse_callback_data(self, data: str) -> Tuple[str, str, Optional[int]]:
        """Parse callback data into action, value, and optional chat_id"""
        parts = data.split(':')
        if len(parts) == 3:  # Group context included
            return parts[0], parts[1], int(parts[2])
        return parts[0], parts[1], None

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        
        try:
            action, value, chat_id = self.parse_callback_data(query.data)
            is_admin = await self._is_admin(update, context, chat_id) if chat_id else True
            
            if action == 'quality':
                await self._handle_quality_callback(query, context, user_id, value, chat_id, is_admin)
            elif action == 'settings':
                await self._handle_settings_callback(query, user_id, value, chat_id, is_admin)
            elif action == 'set_lang':
                await self._handle_language_callback(update, query, user_id, value, chat_id, is_admin)
            elif action == 'set_quality':
                await self._handle_quality_setting_callback(query, user_id, value, chat_id, is_admin)
                
        except Exception as e:
            await query.edit_message_text(
                self.get_message(user_id, 'error_occurred')
            )
            logger.error(f"Error in callback handling: {e}")

    async def _handle_quality_callback(self, query, context, user_id: int, quality: str, chat_id: Optional[int], is_admin: bool):
        """Handle quality selection for download"""
        url = context.user_data.get('pending_url')
        if not url:
            await query.edit_message_text(
                self.get_message(user_id, 'session_expired', chat_id, is_admin)
            )
            return
        
        # Clear stored URL
        context.user_data.clear()
        # Log quality selection if logger is available
        if self.activity_logger:
            self.activity_logger.log_quality_selection(user_id, url, quality)

        # Get downloader
        downloader = DownloaderFactory.get_downloader(url)
        if not downloader:
            await query.edit_message_text(
                self.get_message(user_id, 'invalid_url', chat_id, is_admin)
            )
            return
            return
        
        # Create fake update object for download manager
        class FakeUpdate:
            def __init__(self, effective_user, effective_message):
                self.effective_user = effective_user
                self.effective_message = effective_message

        fake_update = FakeUpdate(
            type('User', (), {'id': user_id})(),
            query.message
        )
        
        # Download with selected format
        await self.download_manager.process_download(
            downloader, 
            url, 
            fake_update,
            query.message, 
            quality
        )

    async def _handle_settings_callback(self, query, user_id: int, setting: str, chat_id: Optional[int], is_admin: bool):
        """Handle settings menu navigation"""
        # For group settings, verify admin status
        if chat_id and chat_id < 0 and not is_admin:
            await query.edit_message_text(
                self.get_message(user_id, 'admin_only', chat_id, is_admin)
            )
            return

        if setting == 'language':
            # Show language selection
            await query.edit_message_text(
                self.get_message(user_id, 'select_language', chat_id, is_admin),
                reply_markup=self.keyboard_builder.build_language_keyboard(user_id, chat_id, is_admin)
            )
            
        elif setting == 'quality':
            # Show quality selection
            await query.edit_message_text(
                self.get_message(user_id, 'select_default_quality', chat_id, is_admin),
                reply_markup=self.keyboard_builder.build_quality_keyboard(user_id, chat_id, is_admin)
            )
            
        elif setting == 'back':
            await self._show_settings_menu(query, user_id, chat_id, is_admin)

    async def _show_settings_menu(self, query, user_id: int, chat_id: Optional[int], is_admin: bool):
        """Show settings menu with current settings"""
        settings = self.settings_manager.get_settings(user_id, chat_id, is_admin)
        quality_display = {
            'ask': self.get_message(user_id, 'ask_every_time', chat_id, is_admin),
            'best': self.get_message(user_id, 'best_available', chat_id, is_admin)
        }.get(settings.default_quality, settings.default_quality)
        
        message = self.get_message(
            user_id,
            'group_settings_menu' if chat_id and chat_id < 0 else 'settings_menu',
            chat_id,
            is_admin,
            language=settings.language.upper(),
            quality=quality_display
        )
        
        await query.edit_message_text(
            message,
            reply_markup=self.keyboard_builder.build_settings_keyboard(user_id, chat_id, is_admin)
        )

    async def _handle_language_callback(self, update, query, user_id: int, language: str, chat_id: Optional[int], is_admin: bool):
        """Handle language setting change"""
        if chat_id and chat_id < 0 and not is_admin:
            await query.edit_message_text(
                self.get_message(user_id, 'admin_only', chat_id, is_admin)
            )
            return

        # Get current settings
        current_settings = self.settings_manager.get_settings(user_id, chat_id, is_admin)
        if current_settings.language == language:
            # Language hasn't changed, show feedback message
            await query.edit_message_text(
                self.get_message(user_id, 'settings_unchanged', chat_id, is_admin)
            )
            return

        self.settings_manager.update_settings(user_id, chat_id=chat_id, is_admin=is_admin, language=language)
        
        # In private chats, update the main keyboard
        if not chat_id or chat_id > 0:
            await update.effective_message.reply_text(
                self.get_message(user_id, 'welcome', chat_id, is_admin),
                reply_markup=self.keyboard_builder.build_main_keyboard(user_id)
            )
        
        await self._show_settings_menu(query, user_id, chat_id, is_admin)

    async def _handle_quality_setting_callback(self, query, user_id: int, quality: str, chat_id: Optional[int], is_admin: bool):
        """Handle quality setting change"""
        if chat_id and chat_id < 0 and not is_admin:
            await query.edit_message_text(
                self.get_message(user_id, 'admin_only', chat_id, is_admin)
            )
            return

        # Get current settings
        current_settings = self.settings_manager.get_settings(user_id, chat_id, is_admin)
        if current_settings.default_quality == quality:
            # Quality hasn't changed, show feedback message
            await query.edit_message_text(
                self.get_message(user_id, 'settings_unchanged', chat_id, is_admin)
            )
            return

        self.settings_manager.update_settings(user_id, chat_id=chat_id, is_admin=is_admin, default_quality=quality)
        await self._show_settings_menu(query, user_id, chat_id, is_admin)




