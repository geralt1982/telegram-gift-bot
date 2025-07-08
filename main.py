#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram import Update, Bot
    from telegram.error import TelegramError
except ImportError as e:
    logger.error(f"Ошибка импорта telegram: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class SimpleGiftBot:
    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        self.TARGET_USER_ID = int(os.getenv("TARGET_USER_ID", "0"))
        self.MONITOR_GROUP = os.getenv("MONITOR_GROUP", "gifts_detector")
        self.GIFT_TRIGGER_TEXT = os.getenv("GIFT_TRIGGER_TEXT", "🔥 A new limited gift has appeared")
        self.SPAM_INTERVAL = float(os.getenv("SPAM_INTERVAL", "3.0"))
        self.SPAM_DURATION = int(os.getenv("SPAM_DURATION", "300"))
        self.SPAM_INTENSITY = int(os.getenv("SPAM_INTENSITY", "5"))
        
        if not self.BOT_TOKEN or not self.TARGET_USER_ID:
            logger.error("BOT_TOKEN или TARGET_USER_ID не найдены!")
            sys.exit(1)
            
        self.application = None
        self.active_spam_tasks = {}
        self.messages_processed = 0
        self.gifts_detected = 0
        self.start_time = datetime.now()
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        welcome_message = f"""
🎁 Gift Detector Bot активен!

Мониторю группу {self.MONITOR_GROUP} для обнаружения подарков.
Когда найду сообщение с "{self.GIFT_TRIGGER_TEXT}", начну спам-уведомления!

Команды:
• /start - Показать это сообщение
• /stop_spam - Остановить спам
• /status - Статус бота
• /help - Помощь

Настройки:
• Пользователь: {self.TARGET_USER_ID}
• Интервал спама: {self.SPAM_INTERVAL}с
• Длительность: {self.SPAM_DURATION}с
• Интенсивность: {self.SPAM_INTENSITY} сообщений

Бот готов к работе! 🚀
        """
        await update.message.reply_text(welcome_message)
        
    async def stop_spam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        if user_id == self.TARGET_USER_ID:
            stopped_count = 0
            for task_user_id in list(self.active_spam_tasks.keys()):
                task = self.active_spam_tasks[task_user_id]
                task.cancel()
                del self.active_spam_tasks[task_user_id]
                stopped_count += 1
                
            if stopped_count > 0:
                await update.message.reply_text(f"✅ Спам остановлен! Остановлено {stopped_count} активных сессий.")
            else:
                await update.message.reply_text("ℹ️ Активных спам-сессий не найдено.")
        else:
            await update.message.reply_text("❌ У вас нет прав для остановки спама.")
            
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        active_spam_count = len(self.active_spam_tasks)
        
        status_message = f"""
📊 Статус бота

Время работы: {uptime_str}
Обработано сообщений: {self.messages_processed}
Найдено подарков: {self.gifts_detected}
Активных спам-сессий: {active_spam_count}

Конфигурация:
• Группа: {self.MONITOR_GROUP}
• Пользователь: {self.TARGET_USER_ID}
• Интервал: {self.SPAM_INTERVAL}с
• Длительность: {self.SPAM_DURATION}с
• Интенсивность: {self.SPAM_INTENSITY}

Статус: {'🟢 Работает' if active_spam_count == 0 else '🟡 Активный спам'}

Обновлено: {datetime.now().strftime('%H:%M:%S')}
        """
        await update.message.reply_text(status_message)
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_message = f"""
🆘 Помощь по Gift Detector Bot

Назначение:
Бот отслеживает группу {self.MONITOR_GROUP} и отправляет агрессивные уведомления при обнаружении подарков.

Команды:
• /start - Запуск и информация
• /stop_spam - Остановить все уведомления
• /status - Показать статус и статистику
• /help - Эта справка

Как работает:
1. Бот мониторит сообщения в группе
2. При обнаружении "{self.GIFT_TRIGGER_TEXT}" активируется спам
3. Отправляются множественные уведомления каждые {self.SPAM_INTERVAL}с
4. Спам длится до {self.SPAM_DURATION}с или до команды /stop_spam
5. Каждая волна содержит {self.SPAM_INTENSITY} сообщений

Удачной охоты за подарками! 🎁
        """
        await update.message.reply_text(help_message)
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            message = update.message
            if not message or not message.text:
                return
                
            self.messages_processed += 1
            
            chat = message.chat
            if not chat:
                return
                
            is_target_group = (
                chat.username == self.MONITOR_GROUP or
                chat.title == self.MONITOR_GROUP or
                str(chat.id) == self.MONITOR_GROUP
            )
            
            if not is_target_group:
                return
                
            if message.text.startswith(self.GIFT_TRIGGER_TEXT):
                self.gifts_detected += 1
                logger.info(f"🎁 ПОДАРОК НАЙДЕН! Сообщение: {message.text[:100]}...")
                await self.start_spam_notifications(context.bot, message.text)
                
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            
    async def start_spam_notifications(self, bot: Bot, original_message: str) -> None:
        try:
            if self.TARGET_USER_ID in self.active_spam_tasks:
                self.active_spam_tasks[self.TARGET_USER_ID].cancel()
                
            task = asyncio.create_task(self.spam_worker(bot, original_message))
            self.active_spam_tasks[self.TARGET_USER_ID] = task
            
        except Exception as e:
            logger.error(f"Ошибка запуска спама: {e}")
            
    async def spam_worker(self, bot: Bot, original_message: str) -> None:
        try:
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=self.SPAM_DURATION)
            
            alert_message = f"""
🚨 ПОДАРОК ОБНАРУЖЕН! ПРОСЫПАЙСЯ! 🚨

🎁 В группе gifts_detector появился новый подарок!

Сообщение:
{original_message}

Время: {start_time.strftime('%H:%M:%S')}

Используй /stop_spam чтобы остановить уведомления.
            """
            
            await bot.send_message(
                chat_id=self.TARGET_USER_ID,
                text=alert_message
            )
            
            message_count = 0
            spam_messages = [
                "🚨 ПРОСЫПАЙСЯ! Подарок #{} обнаружен!",
                "⏰ НЕ ПРОПУСТИ! Уведомление #{}",
                "🎁 ПОДАРОК ДОСТУПЕН! Сообщение #{}",
                "🔥 СРОЧНО: Лимитированный подарок #{}",
                "⚡ ПРОСНИСЬ! Подарок #{} найден!",
                "🚀 БЫСТРЕЕ! Уведомление #{}",
                "💥 ВНИМАНИЕ! Подарок #{} детектирован!",
                "🎯 ПРОСНИСЬ! Важный подарок #{}"
            ]
            
            while datetime.now() < end_time:
                try:
                    for i in range(self.SPAM_INTENSITY):
                        message_count += 1
                        message_text = spam_messages[message_count % len(spam_messages)].format(message_count)
                        
                        await bot.send_message(
                            chat_id=self.TARGET_USER_ID,
                            text=message_text
                        )
                        
                        await asyncio.sleep(0.5)
                        
                    await asyncio.sleep(self.SPAM_INTERVAL)
                    
                except TelegramError as e:
                    logger.error(f"Ошибка отправки спама: {e}")
                    await asyncio.sleep(2)
                    
                except asyncio.CancelledError:
                    logger.info("Спам-задача отменена")
                    break
                    
            if self.TARGET_USER_ID in self.active_spam_tasks:
                final_message = f"""
✅ Спам-сессия завершена

Сводка:
• Длительность: {self.SPAM_DURATION} секунд
• Отправлено сообщений: {message_count}
• Завершено: {datetime.now().strftime('%H:%M:%S')}

Надеюсь, ты проснулся! Используй /stop_spam для остановки будущих уведомлений.
                """
                
                await bot.send_message(
                    chat_id=self.TARGET_USER_ID,
                    text=final_message
                )
                
        except Exception as e:
            logger.error(f"Ошибка в спам-воркере: {e}")
            
        finally:
            if self.TARGET_USER_ID in self.active_spam_tasks:
                del self.active_spam_tasks[self.TARGET_USER_ID]
                
    async def run(self):
        try:
            self.application = Application.builder().token(self.BOT_TOKEN).build()
            
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("stop_spam", self.stop_spam_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            
            self.application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_message
            ))
            
            logger.info("🚀 Запуск Gift Detector Bot...")
            await self.application.run_polling(
                poll_interval=1.0,
                timeout=20,
                read_timeout=20,
                write_timeout=20,
                connect_timeout=20
            )
            
        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            raise

async def main():
    bot = SimpleGiftBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
