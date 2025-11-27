from typing import Dict, Any

# Language codes should match ISO 639-1
LOCALES: Dict[str, Dict[str, str]] = {
    'ru': {
        'welcome': (
            "Zenload\n\n"
            "Отправьте ссылку на видео или музыку с:\n"
            "• Instagram\n"
            "• TikTok\n"
            "• Pinterest\n"
            "• Yandex Music\n"
            "• SoundCloud\n\n"
            "Команды:\n"
            "/settings - Настройки\n"
            "/help - Помощь\n"
            "/donate - Поддержать"
        ),
        'btn_settings': "Настройки",
        'btn_help': "Помощь",
        'btn_language': "Язык",
        'btn_quality': "Качество",
        'btn_back': "Назад",
        'btn_russian': "Русский",
        'btn_english': "English",
        'btn_ask': "Спрашивать каждый раз",
        'btn_best': "Лучшее",
        'btn_donate': "Поддержать",
        'help': (
            "Как использовать:\n\n"
            "1. Отправьте ссылку\n"
            "2. Выберите качество\n"
            "3. Дождитесь загрузки\n\n"
            "Настройки:\n"
            "• Язык интерфейса\n"
            "• Качество по умолчанию\n\n"
            "Примечание: Контент должен быть публичным"
        ),
        'unsupported_url': (
            "Неподдерживаемая ссылка\n\n"
            "Поддерживаются:\n"
            "• Instagram\n"
            "• TikTok\n"
            "• Pinterest\n"
            "• Yandex Music\n"
            "• SoundCloud"
        ),
        'settings_menu': (
            "Настройки\n\n"
            "Язык: {language}\n"
            "Качество: {quality}"
        ),
        'processing': "Обработка...",
        'select_quality': "Выберите качество:",
        'best_quality': "Лучшее",
        'quality_format': "{quality} ({ext})",
        'select_language': "Выберите язык:",
        'select_default_quality': "Качество по умолчанию:",
        'ask_every_time': "Спрашивать",
        'best_available': "Лучшее",
        'downloading': "Загрузка...",
        'session_expired': "Сессия истекла. Отправьте ссылку заново.",
        'invalid_url': "Неверная ссылка",
        'error_occurred': "Произошла ошибка при обработке запроса",
        'download_failed': (
            "Ошибка загрузки: {error}\n\n"
            "Возможные причины:\n"
            "• Приватный аккаунт\n"
            "• Требуется авторизация\n"
            "• Контент удален\n"
            "• Неверная ссылка"
        ),
        'auth_required': (
            "Требуется авторизация\n\n"
            "Возможные причины:\n"
            "• Приватный аккаунт\n"
            "• Неверная ссылка\n"
            "• Временная ошибка"
        ),
        'donate': (
            "Поддержите разработку бота!\n\n"
            "Выберите сумму поддержки в Stars"
        ),
        'invoice_title': "Поддержать Zenload Bot",
        'invoice_description': "Поддержите разработку бота Stars",
        'price_label': "Поддержка (100 Stars)",
        'payment_support': (
            "По вопросам оплаты обращайтесь к @binarybliss"
        ),
        'payment_success': "Спасибо за вашу поддержку!",
        'group_welcome': (
            "Привет! Используйте команду /zen с ссылкой для загрузки видео или музыки.\n"
            "Примеры:\n"
            "• /zen https://www.instagram.com/p/...\n"
            "• /zen https://music.yandex.ru/album/123/track/456"
        ),
        'missing_url': "Пожалуйста, укажите ссылку после команды /zen",
        # Status messages
        'status_getting_info': "Получение информации... ({progress}%)",
        'status_downloading': "Загрузка... ({progress}%)",
        'status_processing': "Обработка... ({progress}%)",
        'status_sending': "Отправка файла... ({progress}%)",
        'admin_only': "Только администраторы могут изменять настройки группы",
        'group_settings_menu': "Настройки группы\n\nЯзык: {language}\nКачество: {quality}",
        'settings_unchanged': "Настройки не изменились",
        # Rate limit and concurrent download messages
        'error_too_many_downloads': (
            "Слишком много одновременных загрузок.\n"
            "Пожалуйста, подождите завершения текущих загрузок или попробуйте позже."
        ),
        'error_rate_limit': "Слишком много запросов. Пожалуйста, подождите несколько секунд."
    },
    'en': {
        'welcome': (
            "Zenload\n\n"
            "Send video or music URL from:\n"
            "• Instagram\n"
            "• TikTok\n"
            "• Pinterest\n"
            "• Yandex Music\n"
            "• SoundCloud\n\n"
            "Commands:\n"
            "/settings - Settings\n"
            "/help - Help\n"
            "/donate - Support"
        ),
        'btn_settings': "Settings",
        'btn_help': "Help",
        'btn_language': "Language",
        'btn_quality': "Quality",
        'btn_back': "Back",
        'btn_russian': "Russian",
        'btn_english': "English",
        'btn_ask': "Ask",
        'btn_best': "Best",
        'btn_donate': "Support",
        'help': (
            "How to use:\n\n"
            "1. Send URL\n"
            "2. Select quality\n"
            "3. Wait for download\n\n"
            "Settings:\n"
            "• Interface language\n"
            "• Default quality\n\n"
            "Note: Content must be public"
        ),
        'unsupported_url': (
            "Unsupported URL\n\n"
            "Supported:\n"
            "• Instagram\n"
            "• TikTok\n"
            "• Pinterest\n"
            "• Yandex Music\n"
            "• SoundCloud"
        ),
        'settings_menu': (
            "Settings\n\n"
            "Language: {language}\n"
            "Quality: {quality}"
        ),
        'processing': "Processing...",
        'select_quality': "Select quality:",
        'best_quality': "Best",
        'quality_format': "{quality} ({ext})",
        'select_language': "Select language:",
        'select_default_quality': "Default quality:",
        'ask_every_time': "Ask every time",
        'best_available': "Best",
        'downloading': "Downloading...",
        'session_expired': "Session expired. Send URL again.",
        'invalid_url': "Invalid URL",
        'error_occurred': "Error processing request",
        'download_failed': (
            "Download failed: {error}\n\n"
            "Possible reasons:\n"
            "• Private account\n"
            "• Authentication required\n"
            "• Content deleted\n"
            "• Invalid URL"
        ),
        'auth_required': (
            "Authentication required\n\n"
            "Possible reasons:\n"
            "• Private account\n"
            "• Invalid URL\n"
            "• Temporary error"
        ),
        'donate': (
            "Support bot development!\n\n"
            "Choose support amount in Stars"
        ),
        'invoice_title': "Support Zenload Bot",
        'invoice_description': "Support bot development with Stars",
        'price_label': "Support (100 Stars)",
        'payment_support': (
            "For payment support, please contact @binarybliss"
        ),
        'payment_success': "Thank you for your support!",
        'group_welcome': (
            "Hi! Use the /zen command with a URL to download videos or music.\n"
            "Examples:\n"
            "• /zen https://www.instagram.com/p/...\n"
            "• /zen https://music.yandex.ru/album/123/track/456"
        ),
        'missing_url': "Please provide a URL after the /zen command",
        # Status messages
        'status_getting_info': "Getting information... ({progress}%)",
        'status_downloading': "Downloading... ({progress}%)",
        'status_processing': "Processing... ({progress}%)",
        'status_sending': "Sending file... ({progress}%)",
        'admin_only': "Only administrators can modify group settings",
        'group_settings_menu': "Group Settings\n\nLanguage: {language}\nQuality: {quality}",
        'settings_unchanged': "Settings remain unchanged",
        # Rate limit and concurrent download messages
        'error_too_many_downloads': (
            "Too many concurrent downloads.\n"
            "Please wait for current downloads to complete or try again later."
        ),
        'error_rate_limit': "Too many requests. Please wait a few seconds."
    }
}

class Localization:
    @staticmethod
    def get(lang: str, key: str, **kwargs) -> str:
        """
        Get localized string by key and format it with provided kwargs
        Falls back to English if key not found in selected language
        """
        try:
            text = LOCALES.get(lang, LOCALES['en'])[key]
            return text.format(**kwargs) if kwargs else text
        except (KeyError, ValueError) as e:
            # Fallback to English if key not found or formatting fails
            try:
                text = LOCALES['en'][key]
                return text.format(**kwargs) if kwargs else text
            except (KeyError, ValueError):
                return f"Missing translation: {key}"
