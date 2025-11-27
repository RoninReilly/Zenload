import logging
import logging.config
from pathlib import Path
import os
import fcntl
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, InlineQueryHandler, filters
import signal
import asyncio
import sys

from .config import TOKEN, LOGGING_CONFIG, BASE_DIR
from .database import UserSettingsManager, UserActivityLogger
from .locales import Localization
from .utils import KeyboardBuilder, DownloadManager
from .utils.soundcloud_service import SoundcloudService
from .handlers import CommandHandlers, MessageHandlers, CallbackHandlers, PaymentHandlers, InlineHandlers

# Configure logging
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

class ZenloadBot:
    def __init__(self):
        self.lock_file = None
        self.lock_fd = None
        
        # Try to acquire lock
        try:
            pid_file = Path("/var/run/zenload.pid")  # Standard Unix PID file location
            if not pid_file.parent.exists():
                pid_file = Path(BASE_DIR) / "zenload.pid"  # Fallback to app directory
            
            self.lock_file = pid_file
            self.lock_fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT, 0o644)
            
            # Try non-blocking lock
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID to file
                os.truncate(self.lock_fd, 0)
                os.write(self.lock_fd, str(os.getpid()).encode())
            except (IOError, OSError) as e:
                logger.error(f"Another instance is already running (Error: {e})")
                os.close(self.lock_fd)
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            if self.lock_fd:
                try:
                    os.close(self.lock_fd)
                except:
                    pass
            sys.exit(1)
            
        # Initialize core components
        self.application = Application.builder().token(TOKEN).build()
        self.settings_manager = UserSettingsManager()
        self.localization = Localization()
        self.activity_logger = UserActivityLogger(self.settings_manager.db)
        self.soundcloud_service = SoundcloudService.get_instance()
        
        # Initialize utility classes
        self.keyboard_builder = KeyboardBuilder(
            self.localization,
            self.settings_manager
        )
        self.download_manager = DownloadManager(
            self.localization,
            self.settings_manager,
            activity_logger=self.activity_logger
        )
        
        # Initialize handlers
        self.command_handlers = CommandHandlers(
            self.keyboard_builder,
            self.settings_manager,
            self.localization
        )
        self.message_handlers = MessageHandlers(
            self.keyboard_builder,
            self.settings_manager,
            self.download_manager,
            self.localization,
            activity_logger=self.activity_logger
        )
        self.callback_handlers = CallbackHandlers(
            self.keyboard_builder,
            self.settings_manager,
            self.download_manager,
            self.localization,
            activity_logger=self.activity_logger
        )
        self.payment_handlers = PaymentHandlers(
            self.localization,
            self.settings_manager
        )
        self.inline_handlers = InlineHandlers(
            self.settings_manager,
            self.localization,
            self.soundcloud_service
        )
        
        self._setup_handlers()
        self._stopping = False

    def _setup_handlers(self):
        """Setup bot command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.command_handlers.start_command))
        self.application.add_handler(CommandHandler("zen", self.command_handlers.zen_command))
        self.application.add_handler(CommandHandler("help", self.command_handlers.help_command))
        self.application.add_handler(CommandHandler("settings", self.command_handlers.settings_command))
        self.application.add_handler(CommandHandler("donate", self.command_handlers.donate_command))
        self.application.add_handler(CommandHandler("paysupport", self.command_handlers.paysupport_command))
        
        # Payment handlers
        self.application.add_handler(PreCheckoutQueryHandler(self.payment_handlers.pre_checkout_callback))
        
        # Message handlers for private chats
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            self.message_handlers.handle_message
        ))
        
        # Message handlers for group chats (with bot mention)
        self.application.add_handler(MessageHandler(
            (filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS & filters.Entity("mention")),
            self.message_handlers.handle_message
        ))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback))

        # Inline query handler for SoundCloud search
        self.application.add_handler(InlineQueryHandler(self.inline_handlers.handle_inline_query))

    async def stop(self):
        """Stop the bot gracefully"""
        if self._stopping:
            return
        
        self._stopping = True
        logger.info("Stopping bot...")
        
        try:
            # Stop accepting new updates first
            if self.application.updater:
                try:
                    await asyncio.wait_for(self.application.updater.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Updater stop timed out")
                except Exception as e:
                    logger.error(f"Error stopping updater: {e}")
            
            # Cleanup download manager
            try:
                if hasattr(self.download_manager, 'cleanup'):
                    await asyncio.wait_for(self.download_manager.cleanup(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Download manager cleanup timed out")
            except Exception as e:
                logger.error(f"Error during download manager cleanup: {e}")
            
            # Stop application
            if self.application.running:
                try:
                    await asyncio.wait_for(self.application.stop(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Application stop timed out")
                except Exception as e:
                    logger.error(f"Error stopping application: {e}")
                
                try:
                    await asyncio.wait_for(self.application.shutdown(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Application shutdown timed out")
                except Exception as e:
                    logger.error(f"Error during application shutdown: {e}")
            
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}", exc_info=True)
        finally:
            # Close SoundCloud session
            try:
                await asyncio.wait_for(self.soundcloud_service.close(), timeout=3)
            except Exception as e:
                logger.warning(f"Error closing SoundCloud service: {e}")

            # Release lock file and cleanup PID file
            if self.lock_fd is not None:
                try:
                    # Release lock
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                    os.close(self.lock_fd)
                    # Remove PID file if it exists and belongs to us
                    if self.lock_file and self.lock_file.exists():
                        try:
                            pid = int(self.lock_file.read_text().strip())
                            if pid == os.getpid():
                                self.lock_file.unlink()
                        except (ValueError, OSError) as e:
                            logger.warning(f"Error cleaning up PID file: {e}")
                except Exception as e:
                    logger.error(f"Error releasing lock: {e}")
            
            self._stopping = False  # Reset stopping flag

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        if self._stopping:
            logger.info("Forced shutdown initiated")
            # Release lock file on forced shutdown
            if self.lock_fd is not None:
                try:
                    # Release lock and cleanup PID file
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                    os.close(self.lock_fd)
                    if self.lock_file and self.lock_file.exists():
                        try:
                            pid = int(self.lock_file.read_text().strip())
                            if pid == os.getpid():
                                self.lock_file.unlink()
                        except (ValueError, OSError) as e:
                            logger.warning(f"Error cleaning up PID file during forced shutdown: {e}")
                except Exception as e:
                    logger.error(f"Error releasing lock during forced shutdown: {e}")
            sys.exit(1)
        
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except Exception as e:
            logger.error(f"Error getting event loop in signal handler: {e}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            loop.create_task(self.stop())
        except Exception as e:
            logger.error(f"Error creating stop task: {e}")
            # Force cleanup if we can't stop gracefully
            if self.lock_fd is not None:
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                    os.close(self.lock_fd)
                except Exception:
                    pass
            sys.exit(1)

    def run(self):
        """Start the bot"""
        logger.info("Starting Zenload bot...")
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Create new event loop and set it as the current one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the application
            self.application.run_polling(drop_pending_updates=True)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            # Ensure cleanup is performed
            if not self._stopping:
                try:
                    # Create new event loop for cleanup if needed
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Run cleanup
                    loop.run_until_complete(self.stop())
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass
