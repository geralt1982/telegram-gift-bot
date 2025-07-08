#!/usr/bin/env python3
"""
Простой Telegram Gift Detector Bot для развертывания на бесплатных платформах
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

class SimpleGiftBot:
    def __init__(self):
        # Получение переменных среды
        self.bot_token = os.getenv('BOT_TOKEN')
        self.target_user_id = int(os.getenv('TARGET_USER_ID', '0'))
        
        if not self.bot_token or not self.target_user_id:
            raise ValueError("BOT_TOKEN и TARGET_USER_ID должны быть установлены!")
        
        # Настройки спама
        self.spam_interval = float(os.getenv('SPAM_INTERVAL', '3.0'))
        self.spam_duration = int(os.getenv('SPAM_DURATION', '300'))
        self.spam_intensity = int(os.getenv('SPAM_INTENSITY', '5'))
        
        # Состояние бота
        self.spam_active = False
        self.spam_task = None
        self.application = None
        
        logger.info(f"Bot initialized for user {self.target_user_id}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /start"""
        await update.message.reply_text(
            "🎁 Бот мониторинга подарков запущен!\n\n"
            "Теперь я слежу за сообщениями о подарках и буду будить вас агрессивными уведомлениями!\n\n"
            "Команды:\n"
            "/start - Запуск бота\n"
            "/stop_spam - Остановить спам\n"
            "/status - Статус бота\n"
            "/help - Помощь"
        )
        logger.info(f"Пользователь {update.effective_user.id} запустил бота")

    async def stop_spam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /stop_spam"""
        if self.spam_active and self.spam_task:
            self.spam_active = False
            self.spam_task.cancel()
            self.spam_task = None
            await update.message.reply_text("✅ Спам уведомления остановлены!")
            logger.info("Спам остановлен по команде пользователя")
        else:
            await update.message.reply_text("ℹ️ Спам сейчас не активен")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /status"""
        status = "🔴 Неактивен" if not self.spam_active else "🟢 Активен"
        await update.message.reply_text(
            f"📊 Статус бота:\n\n"
            f"Спам: {status}\n"
            f"Целевой пользователь: {self.target_user_id}\n"
            f"Интервал: {self.spam_interval}с\n"
            f"Длительность: {self.spam_duration}с\n"
            f"Интенсивность: {self.spam_intensity} сообщений"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /help"""
        await update.message.reply_text(
            "🆘 Помощь по боту мониторинга подарков\n\n"
            "Этот бот следит за сообщениями о подарках в группах и отправляет агрессивные уведомления.\n\n"
            "🔍 Триггеры для поиска подарков:\n"
            "- '🔥 A new limited gift has appeared'\n"
            "- 'подарок'\n"
            "- 'gift'\n\n"
            "📱 Команды:\n"
            "/start - Запуск бота\n"
            "/stop_spam - Остановить спам\n"
            "/status - Показать статус\n"
            "/help - Эта справка\n\n"
            "⚙️ Бот работает 24/7 и мониторит все сообщения!"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка сообщений для поиска подарков"""
        if not update.message or not update.message.text:
            return
            
        message_text = update.message.text.lower()
        
        # Триггеры для обнаружения подарков
        gift_triggers = [
            "🔥 a new limited gift has appeared",
            "подарок",
            "gift",
            "🎁"
        ]
        
        # Проверяем наличие триггеров
        for trigger in gift_triggers:
            if trigger in message_text:
                logger.info(f"Обнаружен подарок! Триггер: '{trigger}' в сообщении: {message_text[:100]}")
                
                # Запускаем спам уведомления
                if not self.spam_active:
                    await self.start_spam_notifications(context.bot, update.message.text)
                break

    async def start_spam_notifications(self, bot: Bot, original_message: str) -> None:
        """Запуск спам-уведомлений"""
        if self.spam_active:
            return
            
        self.spam_active = True
        logger.info("Запуск агрессивных уведомлений о подарке!")
        
        # Запускаем задачу спама
        self.spam_task = asyncio.create_task(
            self.spam_worker(bot, original_message)
        )

    async def spam_worker(self, bot: Bot, original_message: str) -> None:
        """Рабочий процесс спама"""
        start_time = datetime.now()
        messages_sent = 0
        
        try:
            while self.spam_active:
                # Проверяем лимит времени
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= self.spam_duration:
                    logger.info(f"Спам завершен по времени ({self.spam_duration}с)")
                    break
                
                # Отправляем пакет сообщений
                for i in range(self.spam_intensity):
                    if not self.spam_active:
                        break
                        
                    try:
                        message = (
                            f"🚨 ПОДАРОК ОБНАРУЖЕН! 🚨\n\n"
                            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n\n"
                            f"📝 Исходное сообщение:\n{original_message[:200]}...\n\n"
                            f"🔥 БЫСТРЕЕ! НЕ ПРОСПИ ПОДАРОК!\n\n"
                            f"📊 Сообщение #{messages_sent + 1}"
                        )
                        
                        await bot.send_message(
                            chat_id=self.target_user_id,
                            text=message
                        )
                        messages_sent += 1
                        
                        # Небольшая пауза между сообщениями в пакете
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Ошибка отправки сообщения: {e}")
                
                # Пауза между пакетами
                await asyncio.sleep(self.spam_interval)
                
        except asyncio.CancelledError:
            logger.info("Задача спама была отменена")
        except Exception as e:
            logger.error(f"Ошибка в spam_worker: {e}")
        finally:
            self.spam_active = False
            self.spam_task = None
            logger.info(f"Спам завершен. Отправлено сообщений: {messages_sent}")

    async def run(self):
        """Запуск бота"""
        try:
            # Создание приложения
            self.application = Application.builder().token(self.bot_token).build()
            
            # Добавление обработчиков
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("stop_spam", self.stop_spam_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            
            # Обработчик всех текстовых сообщений
            self.application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                self.handle_message
            ))
            
            logger.info("Запуск бота...")
            
            # Запуск бота
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
    """Главная функция"""
    try:
        bot = SimpleGiftBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
