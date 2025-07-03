import logging
from typing import Dict
from collections import defaultdict
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from io import BytesIO
from datetime import datetime

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
print(BOT_TOKEN)
# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AccountParser:
    def parse_file(self, content: str) -> list:
        accounts = []
        for line in content.splitlines():
            if line.strip():
                try:
                    account = self._parse_line(line)
                    accounts.append(account)
                except Exception as e:
                    logger.error(f"Error parsing line: {e}")
        return accounts

    def _parse_line(self, line: str) -> dict:
        try:
            # Split only on first occurrence of '|' to separate credentials
            parts = line.split('|', 1)
            credentials = parts[0].strip()
            email, password = credentials.split(':', 1)
            
            # Initialize details dictionary
            parsed_details = {}
            
            # If there are additional details after credentials
            if len(parts) > 1:
                details_part = parts[1]
                # Split remaining parts by '|'
                detail_parts = details_part.split('|')
                
                for detail in detail_parts:
                    if '=' in detail:
                        key, value = detail.split('=', 1)
                        parsed_details[key.strip()] = value.strip()
            
            return {
                'email': email.strip(),
                'password': password.strip(),
                'details': parsed_details,
                'raw': line.strip()
            }
        except Exception as e:
            logger.error(f"Error in _parse_line: {e}")
            raise

class StatsGenerator:
    def generate_stats(self, accounts: list) -> Dict:
        stats = {
            'plans': defaultdict(int),
            'phone': defaultdict(int),
            'country': defaultdict(int),
            'hold': defaultdict(int),
            'payment': defaultdict(int),
            'total': len(accounts)
        }
        
        for account in accounts:
            details = account['details']
            
            # Plan stats
            plan = details.get('Plan', 'Unknown')
            stats['plans'][plan] += 1
            
            # Phone verification stats
            phone_verified = details.get('PhoneVerified', 'Unknown')
            stats['phone'][phone_verified] += 1
            
            # Country stats
            country = details.get('Country', 'Unknown')
            stats['country'][country] += 1
            
            # Hold stats
            hold = details.get('Hold', 'false')
            stats['hold'][hold] += 1
            
            # Payment stats
            payment = details.get('PaymentMethod', 'Unknown')
            stats['payment'][payment] += 1
            
        return dict(stats)

class BotKeyboards:
    @staticmethod
    def main_menu_keyboard():
        keyboard = [
            [
                InlineKeyboardButton("📊 Show Stats", callback_data="show_stats"),
                InlineKeyboardButton("🔍 Filter Accounts", callback_data="filter_menu")
            ],
            [
                InlineKeyboardButton("📥 Export Results", callback_data="export_menu"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def filter_menu_keyboard():
        keyboard = [
            [
                InlineKeyboardButton("💎 By Plan", callback_data="filter_plan"),
                InlineKeyboardButton("🌍 By Country", callback_data="filter_country")
            ],
            [
                InlineKeyboardButton("📱 By Phone", callback_data="filter_phone"),
                InlineKeyboardButton("🔒 By Hold", callback_data="filter_hold")
            ],
            [
                InlineKeyboardButton("💳 By Payment", callback_data="filter_payment")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def dynamic_filter_keyboard(options: list, filter_type: str):
        keyboard = []
        # Create buttons in pairs
        for i in range(0, len(options), 2):
            row = [InlineKeyboardButton(
                options[i], 
                callback_data=f"apply_{filter_type}_{options[i]}"
            )]
            if i + 1 < len(options):
                row.append(InlineKeyboardButton(
                    options[i + 1],
                    callback_data=f"apply_{filter_type}_{options[i + 1]}"
                ))
            keyboard.append(row)
            
        # Add back button
        keyboard.append([InlineKeyboardButton("⬅️ Back to Filters", callback_data="filter_menu")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def export_menu_keyboard():
        keyboard = [
            [
                InlineKeyboardButton("📝 Text Format", callback_data="export_text"),
                InlineKeyboardButton("📊 CSV Format", callback_data="export_csv")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def format_menu_keyboard():
        keyboard = [
            [
                InlineKeyboardButton("📝 Text", callback_data="format_text"),
                InlineKeyboardButton("📊 CSV", callback_data="format_csv")
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def batch_size_keyboard():
        keyboard = [
            [InlineKeyboardButton("All in one", callback_data="batch_all")],
            [
                InlineKeyboardButton("100", callback_data="batch_100"),
                InlineKeyboardButton("200", callback_data="batch_200"),
                InlineKeyboardButton("500", callback_data="batch_500")
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="export_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

class NetflixAccountBot:
    def __init__(self):
        self.parser = AccountParser()
        self.stats_generator = StatsGenerator()
        self.keyboards = BotKeyboards()
        self.user_data = {}  # Store user session data

    # Markdown helper
    @staticmethod
    def _esc(text: str) -> str:
        """Escape underscores for Telegram MarkdownV2"""
        return text.replace('_', '\\_')

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message when the command /start is issued."""
        user_id = update.effective_user.id
        welcome_text = (
            "🎯 *Netflix Account Filter Bot*\n\n"
            "Send me your accounts.txt file to:\n"
            "📊 Get detailed statistics\n"
            "🔍 Filter accounts by different criteria\n"
            "📥 Export filtered results\n\n"
            "Select an option below:"
        )
        await update.message.reply_text(
            welcome_text,
            reply_markup=self.keyboards.main_menu_keyboard(),
            parse_mode='Markdown'
        )

    def format_stats(self, stats: Dict) -> str:
        """Format statistics for display"""
        esc = self._esc
        return (
            "📊 *ACCOUNT ANALYSIS REPORT*\n\n"
            f"📱 *TOTAL ACCOUNTS:* {stats['total']}\n\n"
            "*PLAN DISTRIBUTION:*\n"
            + "\n".join(f"▪️ {esc(plan)}: {count}" for plan, count in stats['plans'].items())
            + "\n\n*PHONE VERIFICATION:*\n"
            + "\n".join(f"▪️ {esc(status)}: {count}" for status, count in stats['phone'].items())
            + "\n\n*COUNTRY DISTRIBUTION:*\n"
            + "\n".join(f"▪️ {esc(country)}: {count}" for country, count in stats['country'].items())
            + "\n\n*HOLD STATUS:*\n"
            + "\n".join(f"▪️ {esc(status)}: {count}" for status, count in stats['hold'].items())
            + "\n\n*PAYMENT METHODS:*\n"
            + "\n".join(f"▪️ {esc(method)}: {count}" for method, count in stats['payment'].items())
        )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle uploaded document."""
        try:
            # Get file
            file = await update.message.document.get_file()
            
            # Download and read file content
            file_content = await file.download_as_bytearray()
            content = file_content.decode('utf-8', errors='ignore')  # Handle encoding issues
            
            # Parse accounts
            accounts = self.parser.parse_file(content)
            
            if not accounts:
                await update.message.reply_text("❌ No valid accounts found in the file!")
                return
                
            # Generate stats
            stats = self.stats_generator.generate_stats(accounts)
            
            # Store in user session
            user_id = update.effective_user.id
            self.user_data[user_id] = {
                'accounts': accounts,
                'stats': stats
            }
            
            # Show stats
            try:
                stats_message = self.format_stats(stats)
                await update.message.reply_text(
                    stats_message,
                    reply_markup=self.keyboards.main_menu_keyboard(),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending stats: {e}")
                # Fallback message without markdown
                await update.message.reply_text(
                    f"✅ Processed {len(accounts)} accounts.\nSelect an option:",
                    reply_markup=self.keyboards.main_menu_keyboard()
                )
            
        except Exception as e:
            logger.error(f"Error handling document: {e}")
            await update.message.reply_text(
                "❌ Error processing the file. Please make sure it's a valid text file with correct format."
            )

    def filter_accounts(self, accounts: list, filter_type: str, value: str) -> list:
        """Filter accounts based on criteria"""
        filtered = []
        for account in accounts:
            details = account['details']
            
            if filter_type == "plan":
                if details.get('Plan', '').lower() == value.lower():
                    filtered.append(account)
                    
            elif filter_type == "country":
                if details.get('Country', '').lower() == value.lower():
                    filtered.append(account)
                    
            elif filter_type == "phone":
                phone_status = details.get('PhoneVerified', 'Unknown').lower()
                if (value == "Verified" and phone_status == "true") or \
                   (value == "Unverified" and phone_status in ["false", "null", "unknown"]):
                    filtered.append(account)
                    
            elif filter_type == "hold":
                hold_status = details.get('Hold', 'false').lower()
                if (value == "On Hold" and hold_status == "true") or \
                   (value == "Active" and hold_status == "false"):
                    filtered.append(account)
                    
            elif filter_type == "payment":
                if details.get('PaymentMethod', 'Unknown').lower() == value.lower():
                    filtered.append(account)
                    
        return filtered

    def format_filtered_accounts(self, accounts: list, format_type: str) -> tuple:
        """Format filtered accounts for export and return content and filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            if format_type == "text":
                # Return raw lines exactly as input to preserve original formatting
                content = "\n".join(acc['raw'] for acc in accounts)
                filename = f"netflix_accounts_{timestamp}.txt"
                
            elif format_type == "csv":
                header = "Email,Password,Plan,Country,PhoneVerified,Hold,PaymentMethod"
                rows = [header]
                for acc in accounts:
                    details = acc['details']
                    row = [
                        acc['email'],
                        acc['password'],
                        details.get('Plan', ''),
                        details.get('Country', ''),
                        details.get('PhoneVerified', ''),
                        details.get('Hold', ''),
                        details.get('PaymentMethod', '')
                    ]
                    escaped_row = []
                    for cell in row:
                        cell_str = str(cell).replace("\"", "\"\"")
                        escaped_row.append(f'"{cell_str}"')
                    row = escaped_row
                    rows.append(','.join(row))
                content = "\n".join(rows)
                filename = f"netflix_accounts_{timestamp}.csv"
                
            return content, filename
        except Exception as e:
            logger.error(f"Error in format_filtered_accounts: {e}")
            raise

    async def send_export_files(self, chat_id, accounts: list, fmt: str, batch_size: int, context: ContextTypes.DEFAULT_TYPE, label: str="filtered"):
        """Send filtered accounts as one or multiple files depending on batch_size (0 => all in one)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_prefix = f"{label}_{timestamp}"
        if batch_size:
            base_prefix = f"{label}_{batch_size}x_{timestamp}"

        content, _ = self.format_filtered_accounts(accounts, fmt)

        if batch_size == 0 or len(accounts) <= batch_size:
            filename = f"{base_prefix}.txt" if fmt=="text" else f"{base_prefix}.csv"
            file_content = BytesIO(content.encode('utf-8', errors='ignore'))
            file_content.name = filename
            await context.bot.send_document(chat_id=chat_id, document=file_content, filename=filename)
            return
        # Split into chunks
        for idx in range(0, len(accounts), batch_size):
            chunk = accounts[idx: idx + batch_size]
            chunk_content, _ = self.format_filtered_accounts(chunk, fmt)
            part = idx // batch_size + 1
            total_parts = (len(accounts) + batch_size - 1) // batch_size
            part_filename = f"{base_prefix}_batch{part}.txt" if fmt=="text" else f"{base_prefix}_batch{part}.csv"
            file_obj = BytesIO(chunk_content.encode('utf-8', errors='ignore'))
            file_obj.name = part_filename
            await context.bot.send_document(chat_id=chat_id, document=file_obj, filename=part_filename)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button clicks."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user_session = self.user_data.get(user_id)
        
        if not user_session and query.data not in ["help", "main_menu"]:
            await query.message.edit_text(
                "❌ Please upload an accounts file first!",
                reply_markup=self.keyboards.main_menu_keyboard()
            )
            return

        if query.data == "show_stats":
            stats_message = self.format_stats(user_session['stats'])
            await query.message.edit_text(
                stats_message,
                reply_markup=self.keyboards.main_menu_keyboard(),
                parse_mode='Markdown'
            )

        elif query.data == "filter_menu":
            await query.message.edit_text(
                "🔍 *Select Filter Type:*",
                reply_markup=self.keyboards.filter_menu_keyboard(),
                parse_mode='Markdown'
            )

        elif query.data == "filter_plan":
            plans = list(user_session['stats']['plans'].keys())
            await query.message.edit_text(
                "💎 *Select Plan Type:*",
                reply_markup=self.keyboards.dynamic_filter_keyboard(plans, "plan"),
                parse_mode='Markdown'
            )

        elif query.data == "filter_country":
            countries = list(user_session['stats']['country'].keys())
            await query.message.edit_text(
                "🌍 *Select Country:*",
                reply_markup=self.keyboards.dynamic_filter_keyboard(countries, "country"),
                parse_mode='Markdown'
            )

        elif query.data == "filter_phone":
            options = ["Verified", "Unverified"]
            await query.message.edit_text(
                "📱 *Select Phone Status:*",
                reply_markup=self.keyboards.dynamic_filter_keyboard(options, "phone"),
                parse_mode='Markdown'
            )

        elif query.data == "filter_hold":
            options = ["On Hold", "Active"]
            await query.message.edit_text(
                "🔒 *Select Hold Status:*",
                reply_markup=self.keyboards.dynamic_filter_keyboard(options, "hold"),
                parse_mode='Markdown'
            )

        elif query.data == "filter_payment":
            payments = list(user_session['stats']['payment'].keys())
            await query.message.edit_text(
                "💳 *Select Payment Method:*",
                reply_markup=self.keyboards.dynamic_filter_keyboard(payments, "payment"),
                parse_mode='Markdown'
            )

        elif query.data.startswith("apply_"):
            _, filter_type, *value = query.data.split("_")
            value = "_".join(value)
            
            filtered_accounts = self.filter_accounts(user_session['accounts'], filter_type, value)
            
            if not filtered_accounts:
                await query.message.edit_text(
                    f"❌ No accounts found with {filter_type}: {value}",
                    reply_markup=self.keyboards.filter_menu_keyboard()
                )
                return
                
            # Store filtered results in session
            user_session['filtered'] = filtered_accounts
            user_session['filter_label'] = f"{filter_type}_{value}".replace(' ', '').replace('/', '').lower()
            
            result_text = (
                f"✅ Found {len(filtered_accounts)} accounts with {filter_type}: {value}\n\n"
                "Select an export format to get the accounts:"
            )
            
            await query.message.edit_text(
                result_text,
                reply_markup=self.keyboards.format_menu_keyboard(),
                parse_mode='Markdown'
            )

        elif query.data == "export_menu":
            if 'filtered' not in user_session:
                await query.message.edit_text(
                    "❌ Please apply a filter first!",
                    reply_markup=self.keyboards.filter_menu_keyboard()
                )
                return
            await query.message.edit_text(
                "📥 *Choose export format*:",
                reply_markup=self.keyboards.format_menu_keyboard(),
                parse_mode='Markdown'
            )

        # Step-1 format selected
        elif query.data.startswith("format_"):
            fmt = query.data.split("_")[1]
            user_session['export_format'] = fmt
            await query.message.edit_text(
                "🔢 *Choose accounts per file*:",
                reply_markup=self.keyboards.batch_size_keyboard(),
                parse_mode='Markdown'
            )

        # Step-2 batch size selected
        elif query.data.startswith("batch_"):
            if 'filtered' not in user_session or 'export_format' not in user_session:
                await query.message.edit_text(
                    "❌ Please select format first!",
                    reply_markup=self.keyboards.format_menu_keyboard()
                )
                return
            size_token = query.data.split("_")[1]
            batch_size = 0 if size_token == "all" else int(size_token)
            fmt = user_session['export_format']
            label = user_session.get('filter_label', 'filtered')
            await self.send_export_files(
                chat_id=update.effective_chat.id,
                accounts=user_session['filtered'],
                fmt=fmt,
                batch_size=batch_size,
                context=context,
                label=label
            )
            await query.message.edit_text(
                "✅ Export complete! What would you like to do next?",
                reply_markup=self.keyboards.main_menu_keyboard()
            )

        elif query.data == "main_menu":
            await query.message.edit_text(
                "🎯 *Main Menu*\nSelect an option:",
                reply_markup=self.keyboards.main_menu_keyboard(),
                parse_mode='Markdown'
            )

        elif query.data == "help":
            help_text = (
                "*📖 Help Guide*\n\n"
                "1. Upload your accounts.txt file\n"
                "2. View detailed statistics\n"
                "3. Filter accounts by various criteria\n"
                "4. Export filtered results\n\n"
                "File format should be:\n"
                "`email:password | key1 = value1 | key2 = value2`"
            )
            await query.message.edit_text(
                help_text,
                reply_markup=self.keyboards.main_menu_keyboard(),
                parse_mode='Markdown'
            )

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    bot = NetflixAccountBot()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 