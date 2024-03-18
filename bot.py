import datetime
import json
import os
import shutil

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto, 
    Update, 
)

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler, 
    MessageHandler,
)

import scraper
import train_arrival
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
NORMAL, CAPTCHA_VERIFICATION = range(2)
SUPPORTED_MRT_LINES = ["NS", "EW", "CC", "TE", "CE"]
NOT_SUPPORTED_MRT_LINES = ["BP", "NE", "DT"]
NON_OPERATIONAL_STATION_CODES = ["TE10", "TE21"]

# ---------------------------------------------------------------------------- #

"""
CLEANING UP NAMES OF ALL STATIONS
"""
all_stations = json.loads(train_arrival.get_all_station_info())
station_name_map = {}

remove_chars = " -"
for station in all_stations["results"]:
    station_name = station["name"]
    station_lines = station["line"].split(",")
    station_codes = station["code"].split(",")
    
    is_station_supported = False
    for line in station_lines:
        if line in SUPPORTED_MRT_LINES:
            is_station_supported = True
            break
    
    for code in station_codes:
        if code in NON_OPERATIONAL_STATION_CODES:
            is_station_supported = False
            break
        
    if not is_station_supported:
        continue
    
    command_friendly_name = station_name
    for char in remove_chars:
        command_friendly_name = command_friendly_name.replace(char, "").lower()
        
    station_name_map[command_friendly_name] = {
        "original": station_name,
        "codes": station_codes,
        "lines": station_lines
    
    }

# ---------------------------------------------------------------------------- #

"""
UTILITIES
"""
async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Sending captcha to", update.message.from_user.full_name)
    captcha_id = scraper.extract_images_with_selenium()
    context.chat_data["captcha_id"] = captcha_id
    await update.message.reply_media_group(media=[InputMediaPhoto(media=open(scraper.CAPTCHA_IMAGE, "rb"), caption="Help me read the captcha!")])
    return CAPTCHA_VERIFICATION

async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Prompting commands to", update.message.from_user.full_name)
    await update.message.reply_text("Enter the command for a station.", parse_mode="HTML")
    return NORMAL

"""
Format arrival time message
"""
# Example of arrival_data
# arrival_data = {
#     "North-South Line": [
#         {"timing": "...", "destination": "Marina South Pier"},
#         {"timing": "...", "destination": "Marina South Pier"},
#           {"timing": "...", "destination": "Jurong East"},
#           {"timing": "...", "destination": "Jurong East"},
#     ],
#     "East-West Line": [
#         {"timing": "...", "destination": "Pasir Ris"},
#         {"timing": "...", "destination": "Pasir Ris"},
#         {"timing": "...", "destination": "Tuas Link"},
#         {"timing": "...", "destination": "Tuas Link"},
#     ]
# }
def format_arrival_time_message(arrival_data: str) -> str:
    message = ""
    
    for mrt_line, data in arrival_data.items():
        for i in range(len(data)):
            item = data[i]
            timing, destination = item

            if i % 2 == 0:
                message += f"{mrt_line} in the direction of <b>{destination}</b>\n"
                message += f"Next train: <b>{timing}</b>\nFinal Dest: {destination}\n"                
            else:
                message += f"Subsequent train: <b>{timing}</b>\nFinal Dest: {destination}\n"
                message += "\n"
    message += f"Last updated: {datetime.datetime.now().strftime('%d %b %Y %H:%M:%S')}"
    return message

# ---------------------------------------------------------------------------- #

async def get_system_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = "Here is the system map!"
    await update.message.reply_media_group(
        media=[InputMediaPhoto(media=open("network_map.jpg", "rb"), caption=message)])

# ---------------------------------------------------------------------------- #

"""
1. /start command to initialize the bot and send captcha
"""
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: 
    print(update.message.from_user.full_name, "started the bot.")
    if not scraper.is_verified:
        print("(start) Not verified yet.")
        return await send_captcha(update, context)
    else: 
        print("(start) Already verified.")
        return await prompt_command(update, context)
        
"""
2. Enter captcha code in input field
"""
async def enter_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Entering captcha code from", update.message.from_user.full_name)
    if scraper.is_verified:
        print("(captcha) Already verified.")
        return await prompt_command(update, context)

    if "captcha_id" not in context.chat_data or context.chat_data["captcha_id"] != scraper.captcha_id:
        print("Captcha ID mismatch.")
        await update.message.reply_text("Captcha is outdated.")
        return await send_captcha(update, context)
    
    is_valid = scraper.enter_verification_code(update.message.text)
    
    print(f"Captcha code is {'valid' if is_valid else 'invalid'}.")
    if not is_valid:
        await update.message.reply_text("Incorrect catpcha code", parse_mode="HTML")
        return await send_captcha(update, context)
    else:
        await update.message.reply_text("Yay! Enter a station.", parse_mode="HTML")
        return NORMAL

"""
3. Get all stations and select station
"""
async def list_all_stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = ""
    return await update.message.reply_text(message, parse_mode="HTML")

async def get_station_arrival_time(station: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    station_info = station_name_map[station]
    print(f"{update.message.from_user.full_name} requested station: {station} ({station_info['original']})")
    
    if not scraper.is_verified:
        print("(station) Not verified yet.")
        return await send_captcha(update, context)
    
    context.chat_data["codes"] = station_info["codes"]
    
    # Ask scraper to select station from dropdown
    selected_option = scraper.select_station(station_info["codes"])
    
    # Ask scraper to extract the arrival time from website
    arrival_data = scraper.get_arrival_info_station(selected_option)
    message = format_arrival_time_message(arrival_data)

    # Add refresh button
    keyboard = [[InlineKeyboardButton("Refresh 🔄", callback_data="1")],]
    await update.message.reply_text(message, 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    return NORMAL

async def handle_refresh_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"{update.callback_query.from_user.full_name} clicked refresh button.")
    
    query = update.callback_query
    await query.answer()
    
    arrival_data = scraper.refresh_arrival_time(context.chat_data["codes"])
    message = format_arrival_time_message(arrival_data)

    keyboard = [[InlineKeyboardButton("Refresh 🔄", callback_data="1")],]
    await query.edit_message_text(message, 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    return NORMAL

"""
4. Invalid station entered
"""
async def fallback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if scraper.is_verified:
        await update.message.reply_text("Invalid station")
        return await prompt_command(update, context)
    else:
        return await send_captcha(update, context)

# ---------------------------------------------------------------------------- #

"""
APPBUILD AND HANDLERS
"""
def main(): 
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    start_command = CommandHandler("start", start)
    station_commands = list(map(
        lambda stn: CommandHandler(f"get{stn}", lambda update, context: get_station_arrival_time(stn, update, context)),
        list(station_name_map.keys())))
    station_commands.extend(
        [
            CommandHandler("showmap", get_system_map),
            CallbackQueryHandler(handle_refresh_button),
            MessageHandler(filters=None, callback=fallback_command),
        ]
    )
    
    conv_handler = ConversationHandler(
        entry_points=[start_command],
        states={
            NORMAL: station_commands,
            CAPTCHA_VERIFICATION: [MessageHandler(filters=None, callback=enter_captcha)],
        },
        fallbacks=[start_command],
        per_message=False
    )
    
    app.add_handler(conv_handler)
    app.run_polling()
    
async def post_init(app: Application) -> None:
    bot_commands = [BotCommand(command="start", description="Start the bot")]
    bot_commands.append(BotCommand(command="showmap", description="Get the system map"))
    bot_commands.extend(list(map(
        lambda stn: BotCommand(command=f"get{stn}", description=f"Get arrival time for {station_name_map[stn]['original']}"),
        list(station_name_map.keys()))))

    clear_captcha_image()
    await app.bot.set_my_commands(bot_commands)

def clear_captcha_image() -> None:
    folder = os.getcwd() + '/captchas/'
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
            
if __name__ == "__main__":
    main()
