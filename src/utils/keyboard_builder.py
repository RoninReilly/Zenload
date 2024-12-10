from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import Optional

class KeyboardBuilder:
    def __init__(self, localization, settings_manager):
        self.localization = localization
        self.settings_manager = settings_manager

    def get_message(self, user_id: int, key: str, chat_id: Optional[int] = None, is_admin: bool = False, **kwargs) -> str:
        """Get localized message"""
        settings = self.settings_manager.get_settings(user_id, chat_id, is_admin)
        return self.localization.get(settings.language, key, **kwargs)

    def build_main_keyboard(self, user_id: int) -> ReplyKeyboardMarkup:
        """Build main keyboard with common actions - only for private chats"""
        keyboard = [
            [
                KeyboardButton(self.get_message(user_id, 'btn_settings')),
                KeyboardButton(self.get_message(user_id, 'btn_help')),
                KeyboardButton(self.get_message(user_id, 'btn_donate'))
            ]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def build_settings_keyboard(self, user_id: int, chat_id: Optional[int] = None, is_admin: bool = False) -> InlineKeyboardMarkup:
        """Build settings menu keyboard based on context"""
        # For groups, add context to callback data
        context = f":{chat_id}" if chat_id and chat_id < 0 else ""
        
        keyboard = [
            [
                InlineKeyboardButton(
                    self.get_message(user_id, 'btn_language', chat_id, is_admin),
                    callback_data=f"settings:language{context}"
                ),
                InlineKeyboardButton(
                    self.get_message(user_id, 'btn_quality', chat_id, is_admin),
                    callback_data=f"settings:quality{context}"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)

    def build_language_keyboard(self, user_id: int, chat_id: Optional[int] = None, is_admin: bool = False) -> InlineKeyboardMarkup:
        """Build language selection keyboard"""
        context = f":{chat_id}" if chat_id and chat_id < 0 else ""
        
        keyboard = [
            [
                InlineKeyboardButton(
                    self.get_message(user_id, 'btn_russian', chat_id, is_admin),
                    callback_data=f"set_lang:ru{context}"
                ),
                InlineKeyboardButton(
                    self.get_message(user_id, 'btn_english', chat_id, is_admin),
                    callback_data=f"set_lang:en{context}"
                )
            ],
            [InlineKeyboardButton(
                self.get_message(user_id, 'btn_back', chat_id, is_admin),
                callback_data=f"settings:back{context}"
            )]
        ]
        return InlineKeyboardMarkup(keyboard)

    def build_quality_keyboard(self, user_id: int, chat_id: Optional[int] = None, is_admin: bool = False) -> InlineKeyboardMarkup:
        """Build quality selection keyboard"""
        context = f":{chat_id}" if chat_id and chat_id < 0 else ""
        
        keyboard = [
            [InlineKeyboardButton(
                self.get_message(user_id, 'btn_ask', chat_id, is_admin),
                callback_data=f"set_quality:ask{context}"
            )],
            [InlineKeyboardButton(
                self.get_message(user_id, 'btn_best', chat_id, is_admin),
                callback_data=f"set_quality:best{context}"
            )],
            [InlineKeyboardButton(
                self.get_message(user_id, 'btn_back', chat_id, is_admin),
                callback_data=f"settings:back{context}"
            )]
        ]
        return InlineKeyboardMarkup(keyboard)

    def build_format_selection_keyboard(self, user_id: int, formats: list, chat_id: Optional[int] = None, is_admin: bool = False) -> InlineKeyboardMarkup:
        """Build format selection keyboard for downloads"""
        context = f":{chat_id}" if chat_id and chat_id < 0 else ""
        
        keyboard = []
        for fmt in formats:
            keyboard.append([InlineKeyboardButton(
                self.get_message(
                    user_id,
                    'quality_format',
                    chat_id,
                    is_admin,
                    quality=fmt['quality'],
                    ext=fmt['ext']
                ),
                callback_data=f"quality:{fmt['id']}{context}"
            )])
        keyboard.append([InlineKeyboardButton(
            self.get_message(user_id, 'best_quality', chat_id, is_admin),
            callback_data=f"quality:best{context}"
        )])
        return InlineKeyboardMarkup(keyboard)

