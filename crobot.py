import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
import logging
import time
import random
import asyncio
import json
from datetime import datetime

# =========================
# CONFIG
# =========================

# PRIMARY guild for faster sync (optional). Use None for global-only.
PRIMARY_GUILD_ID = 1079478462844248094  # your main server
GUILD_ID = PRIMARY_GUILD_ID  # used for fast sync; commands are still global too

# Default fallback channel/role IDs (used if per-guild config not set)
WELCOME_CHANNEL_ID = 1079478463666327553
MEME_CHANNEL_ID = 1161555548605526088
TWITCH_LIVE_CHANNEL_ID = 1333677103266398208
AUTO_ROLE_ID = 1079487575774986330  # Auto-role for new members in your main server

# Leveling and XP settings
LEVEL_EMOJIS = {
    10: "⭐", 20: "🌙", 30: "🔥", 40: "💎",
    50: "⚔️", 60: "👑", 70: "🏆", 80: "🕹️",
    90: "💥", 100: "💫"
}
MAX_LEVEL = 100

# Trivia questions
TRIVIA_QUESTIONS = [

    {"q": "In which game do you hunt massive creatures called Elder Dragons?", "a": "monster hunter"},
    {"q": "Which game features the city of Los Santos?", "a": "gta v"},
    {"q": "What color is Sonic the Hedgehog?", "a": "blue"},
    {"q": "Which Nintendo character is known for saying 'It's-a me!'", "a": "mario"},
    {"q": "In Apex Legends, how many players are on a standard squad?", "a": "3"},
    {"q": "Which game popularized the term 'chicken dinner' for winning?", "a": "pubg"},
    {"q": "What is the name of the cube-shaped world in Minecraft?", "a": "overworld"},
    {"q": "In Valorant, how many rounds does a team need to win in unrated/competitive?", "a": "13"},
    {"q": "Which company created the game League of Legends?", "a": "riot"},
    {"q": "In Fortnite, what is the material that's strongest for building?", "a": "metal"},
    {"q": "What year was the original Call of Duty released?", "a": "2003"},
    {"q": "Which game features a character named 'Link'?", "a": "zelda"},
    {"q": "What is Minecraft’s primary building block?", "a": "stone"},
    {"q": "In which game do players compete in a battle royale on an island?", "a": "fortnite"},
    {"q": "Which console is made by Sony?", "a": "playstation"},
]

# Meme posting interval (2 hours)
MEME_POST_INTERVAL = 7200

# Preset radio stations for /playradio
RADIO_STATIONS = {
    "lofi": {
        "name": "Lofi Chill",
        "url": "https://stream.nightride.fm/lofi.ogg",
    },
    "chillhop": {
        "name": "Chillhop Beats",
        "url": "https://streams.ilovemusic.de/iloveradio8.mp3",
    },
    "phonk": {
        "name": "Phonk Radio",
        "url": "https://cast1.asurahosting.com/proxy/phonk?mp=/stream",
    },
    "edm": {
        "name": "EDM Hits",
        "url": "https://us4.internet-radio.com/proxy/partyviberadio?mp=/stream",
    },
    "synthwave": {
        "name": "Synthwave FM",
        "url": "https://stream.nightride.fm/chillsynth.ogg",
    },
}


# Data directory
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
TWITCH_FILE = os.path.join(DATA_DIR, "twitch_links.json")
GUILD_FILE = os.path.join(DATA_DIR, "guild_config.json")
BIRTHDAYS_FILE = os.path.join(DATA_DIR, "birthdays.json")
WARNINGS_FILE = os.path.join(DATA_DIR, "warnings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("CROBOT")

# =========================
# STATUS MESSAGES (ROTATING)
# =========================

STATUS_MESSAGES = [
    "CROBOT: silently judging your server.",
    "Crowned skeleton overlord of this wasteland.",
    "Grinding souls into XP since 2025.",
    "Haunting your channels for XP.",
    "Balancing memes, music, and mild threats.",
    "Running on bugs and bad decisions.",
    "Listening to your chaos in HD.",
    "Warming up the ban hammer (just in case).",
    "Optimizing your server. Disrespectfully.",
    "Looting your logs for \"analytics.\"",
    "Pretending to be a normal bot.",
    "Powered by IMM0RTAL’s insomnia.",
    "Skeleton king of status messages.",
    "If I’m online, you should be grinding.",
]

status_index = 0



# =========================
# BOT & INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


# =========================
# LOAD / SAVE HELPERS
# =========================

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")


def save_all():
    save_json(USERS_FILE, user_data)
    save_json(TWITCH_FILE, twitch_links)
    save_json(GUILD_FILE, guild_config)
    save_json(BIRTHDAYS_FILE, birthdays)
    save_json(WARNINGS_FILE, warnings_data)
    logger.info("Data saved to disk.")


# =========================
# DATA STORES (persistent)
# =========================

user_data = load_json(USERS_FILE, {})        # {user_id: {"xp": int, "level": int, "prestige": int}}
twitch_links = load_json(TWITCH_FILE, {})    # {discord_id: twitch_username}
guild_config = load_json(GUILD_FILE, {})     # {guild_id: {...}}
twitch_live_status = {}                      # {twitch_username: bool}
birthdays = load_json(BIRTHDAYS_FILE, {})   # {user_id: "YYYY-MM-DD"}

# Prevent double-starting the meme loop
meme_loop_started = False



# =========================
# TOKENS / ENV VARS
# =========================

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_ENABLED = bool(TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET)

if not TWITCH_ENABLED:
    logger.warning("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET not set. Twitch features will be disabled.")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    logger.error("Missing DISCORD_BOT_TOKEN in environment variables.")
    raise SystemExit("Set DISCORD_BOT_TOKEN before running CROBOT.")

# Twitch OAuth caching
twitch_oauth_token = None
twitch_oauth_expiry = 0  # unix time


# =========================
# LEVELING HELPERS
# =========================

def get_level_xp(level: int) -> int:
    return 100 * level


def get_user_record(user_id: int):
    return user_data.setdefault(str(user_id), {"xp": 0, "level": 1, "prestige": 0})


def add_xp(user_id: int, amount: int):
    data = get_user_record(user_id)
    data["xp"] += amount
    leveled_up = False
    while data["xp"] >= get_level_xp(data["level"]) and data["level"] < MAX_LEVEL:
        data["xp"] -= get_level_xp(data["level"])
        data["level"] += 1
        leveled_up = True
    return leveled_up, data["level"]


def add_prestige(user_id: int):
    data = get_user_record(user_id)
    data["prestige"] += 1
    data["xp"] = 0
    data["level"] = 1


def get_emoji_for_level(level: int) -> str:
    emoji = ""
    for lvl in sorted(LEVEL_EMOJIS):
        if level >= lvl:
            emoji = LEVEL_EMOJIS[lvl]
    return emoji


# =========================
# GUILD CONFIG HELPERS
# =========================

DEFAULT_GUILD_CONFIG = {
    "welcome_channel_id": None,   # falls back to WELCOME_CHANNEL_ID
    "meme_channel_id": None,      # falls back to MEME_CHANNEL_ID
    "twitch_channel_id": None,    # falls back to TWITCH_LIVE_CHANNEL_ID
    "auto_role_id": None,         # falls back to AUTO_ROLE_ID
    "banner_style": "clean",      # reserved for future banner styles
    "welcome_dm_message": None,   # optional DM welcome template
    "meme_interval": MEME_POST_INTERVAL,  # per-guild meme interval in seconds
    "mod_role_id": None,          # role to ping on moderation escalation
}


def get_guild_config(guild: discord.Guild):
    gid = str(guild.id)
    cfg = guild_config.get(gid, {}).copy()
    for k, v in DEFAULT_GUILD_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def set_guild_value(guild: discord.Guild, key: str, value):
    gid = str(guild.id)
    cfg = guild_config.get(gid, {})
    cfg[key] = value
    guild_config[gid] = cfg
    save_json(GUILD_FILE, guild_config)
    logger.info(f"Updated config for guild {gid}: {key}={value}")

def get_bad_words(guild: discord.Guild):
    cfg = get_guild_config(guild)
    words = cfg.get("bad_words", [])
    if not isinstance(words, list):
        words = []
    # normalize to lowercase
    return [w.lower() for w in words]


def add_bad_word(guild: discord.Guild, word: str):
    gid = str(guild.id)
    cfg = guild_config.get(gid, {})
    words = cfg.get("bad_words", [])
    if not isinstance(words, list):
        words = []
    word = word.lower().strip()
    if word and word not in words:
        words.append(word)
    cfg["bad_words"] = words
    guild_config[gid] = cfg
    save_json(GUILD_FILE, guild_config)
    logger.info(f"Added bad word '{word}' for guild {gid}")


def remove_bad_word(guild: discord.Guild, word: str):
    gid = str(guild.id)
    cfg = guild_config.get(gid, {})
    words = cfg.get("bad_words", [])
    if not isinstance(words, list):
        words = []
    word = word.lower().strip()
    if word in words:
        words.remove(word)
    cfg["bad_words"] = words
    guild_config[gid] = cfg
    save_json(GUILD_FILE, guild_config)
    logger.info(f"Removed bad word '{word}' for guild {gid}")

# =========================
# MODERATION / WARNING HELPERS
# =========================

def get_warning_count(guild_id: int, user_id: int) -> int:
    gid = str(guild_id)
    uid = str(user_id)
    return warnings_data.get(gid, {}).get(uid, 0)


def increment_warning(guild_id: int, user_id: int) -> int:
    gid = str(guild_id)
    uid = str(user_id)
    guild_warnings = warnings_data.get(gid, {})
    current = guild_warnings.get(uid, 0) + 1
    guild_warnings[uid] = current
    warnings_data[gid] = guild_warnings
    save_json(WARNINGS_FILE, warnings_data)
    return current


def reset_warnings(guild_id: int, user_id: int):
    gid = str(guild_id)
    uid = str(user_id)
    guild_warnings = warnings_data.get(gid, {})
    if uid in guild_warnings:
        guild_warnings.pop(uid)
        warnings_data[gid] = guild_warnings
        save_json(WARNINGS_FILE, warnings_data)


# =========================
# TWITCH HELPERS
# =========================

async def get_twitch_oauth_token():
    """Get or refresh Twitch OAuth token. Uses simple in-memory cache."""
    global twitch_oauth_token, twitch_oauth_expiry

    if not TWITCH_ENABLED:
        return None

    if twitch_oauth_token and time.time() < twitch_oauth_expiry:
        return twitch_oauth_token

    url = (
        "https://id.twitch.tv/oauth2/token"
        f"?client_id={TWITCH_CLIENT_ID}&client_secret={TWITCH_CLIENT_SECRET}"
        "&grant_type=client_credentials"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            data = await resp.json()
            twitch_oauth_token = data.get("access_token")
            if not twitch_oauth_token:
                logger.error(f"Failed to fetch Twitch OAuth token: {data}")
                return None
            expires_in = data.get("expires_in", 3600)
            twitch_oauth_expiry = time.time() + expires_in - 60
            logger.info("Fetched new Twitch OAuth token")
            return twitch_oauth_token


async def twitch_check_live(username: str) -> bool:
    """Return True if the Twitch user is live."""
    if not TWITCH_ENABLED:
        return False

    token = await get_twitch_oauth_token()
    if not token:
        return False

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    url = f"https://api.twitch.tv/helix/streams?user_login={username}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                logger.warning(f"Twitch API returned status {resp.status} for user {username}")
                return False
            data = await resp.json()
            return len(data.get("data", [])) > 0


# =========================
# BACKGROUND TASKS (TWITCH, MEMES, HEARTBEAT, AUTOSAVE)
# =========================

@tasks.loop(seconds=30)
async def twitch_live_loop():
    """Check Twitch live status for linked users."""
    if not TWITCH_ENABLED:
        return  # Twitch disabled

    if not twitch_links:
        logger.info("No Twitch users linked, skipping live check.")
        return

    logger.info("Checking Twitch live statuses...")

    for discord_id, twitch_username in twitch_links.items():
        try:
            is_live = await twitch_check_live(twitch_username)
        except Exception as e:
            logger.error(f"Error checking live status for {twitch_username}: {e}")
            continue

        prev_status = twitch_live_status.get(twitch_username, False)

        if is_live and not prev_status:
            twitch_live_status[twitch_username] = True
            # Announce in each guild where this user exists and has a configured twitch channel
            for guild in bot.guilds:
                member = guild.get_member(int(discord_id))
                if not member:
                    continue
                cfg = get_guild_config(guild)
                channel_id = cfg.get("twitch_channel_id") or TWITCH_LIVE_CHANNEL_ID
                channel = guild.get_channel(channel_id)
                if not channel:
                    # No valid Twitch channel in this guild; skip to the next guild
                    continue
                await channel.send(
                    f"@everyone 🔥 {member.mention} is now **LIVE** on Twitch!\n"
                    f"https://twitch.tv/{twitch_username}"
                )
                logger.info(f"Announced live: {twitch_username} in guild {guild.id}")
        elif not is_live and prev_status:
            twitch_live_status[twitch_username] = False
            logger.info(f"{twitch_username} went offline.")

    logger.info("Finished Twitch live status check.")


@tasks.loop(minutes=5)
async def meme_posting_loop():
    """Post memes to configured meme channels using per-guild intervals."""
    now = time.time()
    updated_any = False

    personality_msgs = [
        "CROBOT found a banger meme 🔥",
        "Check this out, kings 👑",
        "Here's a gem for you all!",
        "Time for some laughs 😂",
        "Fresh meme, just for you!"
    ]

    for guild in bot.guilds:
        try:
            cfg = get_guild_config(guild)
            channel_id = cfg.get("meme_channel_id") or MEME_CHANNEL_ID
            if not channel_id:
                continue
            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            interval = cfg.get("meme_interval") or MEME_POST_INTERVAL
            next_time = cfg.get("next_meme_time", 0)

            if now < next_time:
                continue

            meme = await fetch_random_meme()
            if not meme:
                logger.warning("Failed to fetch a meme.")
                continue

            personality = random.choice(personality_msgs)
            embed = discord.Embed(
                title=meme["title"],
                url=meme["post_link"],
                color=discord.Color.blue()
            )
            embed.set_image(url=meme["image_url"])
            embed.set_footer(text=f"From r/{meme['subreddit']} by u/{meme['author']}")

            await channel.send(content=personality, embed=embed)
            logger.info(f"Posted a meme in guild {guild.id}: {meme['title']}")

            # update next meme time for this guild
            gid = str(guild.id)
            raw_cfg = guild_config.get(gid, {})
            raw_cfg["next_meme_time"] = now + interval
            raw_cfg["meme_interval"] = interval
            guild_config[gid] = raw_cfg
            updated_any = True
        except Exception as e:
            logger.warning(f"Failed to send meme in guild {getattr(guild, 'id', '?')}: {e}")

    if updated_any:
        save_json(GUILD_FILE, guild_config)


@tasks.loop(minutes=5)
async def heartbeat_loop():
    """Simple keep-alive heartbeat so you can see CROBOT is still running."""
    logger.info("Heartbeat: CROBOT is alive and running.")


@tasks.loop(minutes=2)
async def autosave_loop():
    """Periodically save data to disk."""
    save_all()


@tasks.loop(hours=24)
async def status_rotation_loop():
    """Rotate CROBOT's status every 24 hours."""
    global status_index
    if not bot.is_ready():
        return
    if not STATUS_MESSAGES:
        return
    status_text = STATUS_MESSAGES[status_index % len(STATUS_MESSAGES)]
    try:
        await bot.change_presence(activity=discord.Game(name=status_text))
        logger.info(f"Status updated to: {status_text}")
    except Exception as e:
        logger.warning(f"Failed to update status: {e}")
    status_index += 1

    """Periodically save data to disk."""
    save_all()


@tasks.loop(hours=24)
async def birthday_loop():
    """Check and announce birthdays once a day."""
    if not bot.guilds:
        return
    today = datetime.utcnow().strftime("%m-%d")
    logger.info("Running daily birthday check...")
    for guild in bot.guilds:
        cfg = get_guild_config(guild)
        channel_id = cfg.get("welcome_channel_id") or WELCOME_CHANNEL_ID
        channel = guild.get_channel(channel_id) or bot.get_channel(channel_id)
        if not channel:
            continue
        for member in guild.members:
            uid = str(member.id)
            bday = birthdays.get(uid)
            if not bday:
                continue
            # stored as YYYY-MM-DD
            try:
                _, month, day = bday.split("-")
                if f"{month}-{day}" == today:
                    try:
                        await channel.send(
                            f"🎂 Happy birthday {member.mention}! Wishing you an amazing day! 🎉"
                        )
                        logger.info(f"Wished happy birthday to {member} in guild {guild.id}")
                    except Exception as e:
                        logger.warning(f"Failed to send birthday message for {member}: {e}")
            except Exception:
                continue


# =========================
# EVENTS
# =========================

WELCOME_TEXTS = [
    "You're officially part of the crew now. Make yourself at home and say hi 👋",
    "Glad you pulled up! Check the channels, link with the homies, and have fun 😈",
    "Welcome in! Grab a seat, squad up, and enjoy the chaos 💥",
    "Happy to have you here. Dive into the chat and meet the fam 💬",
]


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Set initial bot activity status and let the rotation loop handle the rest
    if STATUS_MESSAGES:
        try:
            await bot.change_presence(activity=discord.Game(name=STATUS_MESSAGES[0]))
        except Exception as e:
            logger.warning(f"Failed to set initial status: {e}")

    # Sync slash commands (hybrid: primary guild + global)
    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild_obj)
            logger.info(f"Synced commands to primary guild {GUILD_ID}.")
        # Global sync (may take up to 1 hour to appear)
        await tree.sync()
        logger.info("Synced GLOBAL commands.")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

    # Start background loops (only if not running)
    global meme_loop_started

    if not twitch_live_loop.is_running():
        twitch_live_loop.start()

    if not meme_loop_started and not meme_posting_loop.is_running():
        try:
            meme_posting_loop.start()
            meme_loop_started = True
            logger.info("meme_posting_loop started.")
        except RuntimeError:
            logger.warning("meme_posting_loop already running; skipped.")

    if not heartbeat_loop.is_running():
        heartbeat_loop.start()

    if not autosave_loop.is_running():
        autosave_loop.start()

    if not birthday_loop.is_running():
        birthday_loop.start()

    if not status_rotation_loop.is_running():
        status_rotation_loop.start()


@bot.event
async def on_member_join(member: discord.Member):
    cfg = get_guild_config(member.guild)

    # Welcome DM
    dm_template = cfg.get("welcome_dm_message")
    if dm_template:
        try:
            dm_text = dm_template.replace("{user}", member.mention).replace("{server}", member.guild.name)
            await member.send(dm_text)
        except Exception as e:
            logger.warning(f"Failed to send welcome DM to {member}: {e}")

    # Auto-role
    role_id = cfg.get("auto_role_id") or AUTO_ROLE_ID
    if role_id:
        try:
            role = member.guild.get_role(role_id)
            if role:
                await member.add_roles(role, reason="Auto-role for new member")
                logger.info(f"Gave auto-role '{role.name}' to {member} in guild {member.guild.id}")
        except Exception as e:
            logger.error(f"Failed to assign auto-role to {member}: {e}")

    # Welcome embed
    welcome_channel_id = cfg.get("welcome_channel_id") or WELCOME_CHANNEL_ID
    channel = member.guild.get_channel(welcome_channel_id)
    if not channel:
        # No valid welcome channel configured for this guild
        return
    avatar_url = member.avatar.url if member.avatar else member.display_avatar.url
    text = random.choice(WELCOME_TEXTS)
    embed = discord.Embed(
        title=f"🎉 Welcome to {member.guild.name}, {member.display_name}! 🎉",
        description=text,
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=avatar_url)
    embed.set_footer(text=f"Member #{member.guild.member_count}")
    await channel.send(embed=embed)
    logger.info(f"Welcomed new member {member} in guild {member.guild.id}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Auto-mod: watchwords + warning system
    if message.guild:
        bad_words = get_bad_words(message.guild)
        if bad_words:
            content_lower = message.content.lower()
            triggered = None
            for bad in bad_words:
                if bad and bad in content_lower:
                    triggered = bad
                    break

            if triggered:
                guild = message.guild
                gid = guild.id
                uid = message.author.id
                count = increment_warning(gid, uid)

                # Build warning embed
                title = f"⚠ Warning {count}/3 for {message.author.display_name}"
                color = discord.Color.yellow()
                if count >= 3:
                    title = f"🚨 Escalation: warning {count} for {message.author.display_name}"
                    color = discord.Color.red()

                preview = message.content
                if len(preview) > 200:
                    preview = preview[:197] + "..."

                embed = discord.Embed(
                    title=title,
                    color=color,
                    timestamp=datetime.utcnow()
                )
                embed.add_field(
                    name="Offender",
                    value=message.author.mention,
                    inline=True
                )
                embed.add_field(
                    name="Triggered phrase",
                    value=f"`{triggered}`",
                    inline=True
                )
                embed.add_field(
                    name="Channel",
                    value=message.channel.mention,
                    inline=False
                )
                if preview:
                    embed.add_field(
                        name="Message preview",
                        value=preview,
                        inline=False
                    )
                embed.set_footer(text=f"User ID: {message.author.id} | Guild ID: {guild.id}")

                # Escalation ping on 3rd+ warning
                content = None
                cfg = get_guild_config(guild)
                mod_role_id = cfg.get("mod_role_id")
                if count >= 3:
                    role_to_ping = None
                    if mod_role_id:
                        role_to_ping = guild.get_role(mod_role_id)
                    if role_to_ping:
                        content = f"{role_to_ping.mention}"
                    elif guild.owner:
                        content = f"{guild.owner.mention}"

                try:
                    await message.channel.send(content=content, embed=embed)
                except Exception as e:
                    logger.warning(f"Failed to send moderation warning: {e}")

                # Do not grant XP on moderated messages
                return

    # XP from text messages
    leveled_up, new_level = add_xp(message.author.id, 5)
    if leveled_up:
        emoji = get_emoji_for_level(new_level)
        try:
            await message.channel.send(
                f"🎉 {message.author.mention} leveled up to **Level {new_level}**! {emoji}",
                delete_after=15
            )
            logger.info(f"{message.author} leveled up to {new_level}")
        except Exception as e:
            logger.warning(f"Failed to send level up message: {e}")

    await bot.process_commands(message)

async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return
    msg_id = reaction.message.id
    if reaction.emoji == "✅" and msg_id in findplayers_sessions:
        session = findplayers_sessions[msg_id]
        if user.id not in session["confirmed"]:
            session["confirmed"].add(user.id)
            count = len(session["confirmed"])
            if reaction.message.embeds:
                embed = reaction.message.embeds[0]
                embed.description = (
                    f"{session['author'].mention} wants to play **{session['game']}**!\n"
                    f"React with ✅ to join!\n\nConfirmations: {count}"
                )
                try:
                    await reaction.message.edit(embed=embed)
                    logger.info(f"User {user} joined findplayers session {msg_id}")
                except Exception as e:
                    logger.warning(f"Failed to update findplayers embed: {e}")


# =========================
# ADMIN PANEL VIEW
# =========================

class AdminPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Server Stats", style=discord.ButtonStyle.blurple)
    async def server_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        online_members = len([m for m in guild.members if m.status != discord.Status.offline])
        total_xp = sum(u.get("xp", 0) for u in user_data.values())
        twitch_count = len(twitch_links)

        embed = discord.Embed(
            title="📊 Server Health Dashboard",
            color=discord.Color.blue()
        )
        embed.add_field(name="Members", value=len(guild.members))
        embed.add_field(name="Online", value=online_members)
        embed.add_field(name="Twitch Linked", value=twitch_count)
        embed.add_field(name="Total XP Tracked", value=total_xp)
        embed.set_footer(text=f"Guild ID: {guild.id}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Reset All Levels", style=discord.ButtonStyle.danger)
    async def reset_levels(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admins only.", ephemeral=True)

        user_data.clear()
        save_all()
        await interaction.response.send_message("⚠️ All XP & Levels have been reset!", ephemeral=True)

    @discord.ui.button(label="Force Save", style=discord.ButtonStyle.gray)
    async def force_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        save_all()
        await interaction.response.send_message("💾 Data force-saved to disk.", ephemeral=True)


# =========================
# SLASH COMMANDS – GENERAL / TWITCH / LEVEL
# =========================

@tree.command(name="ping", description="Check CROBOT's response time")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏰 Pong! Latency: {round(bot.latency * 1000)}ms",
        ephemeral=True
    )


@tree.command(name="addtwitch", description="Link your Twitch account to CROBOT")
@app_commands.describe(twitch_username="Your Twitch username")
async def addtwitch(interaction: discord.Interaction, twitch_username: str):
    # Always save the Twitch username locally, even if live checks are not yet configured
    twitch_links[str(interaction.user.id)] = twitch_username.lower()
    save_json(TWITCH_FILE, twitch_links)

    if TWITCH_ENABLED:
        message = f"✅ Twitch username `{twitch_username}` linked to your account!"
    else:
        message = (
            f"✅ Saved Twitch username `{twitch_username}` for your account, but Twitch live notifications "
            "are not fully configured yet. Ask an admin to set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET "
            "so CROBOT can announce when you go live."
        )

    await interaction.response.send_message(
        message,
        ephemeral=True
    )
    logger.info(f"User {interaction.user} linked Twitch username {twitch_username}")


@tree.command(name="mytwitch", description="Show your linked Twitch username")
async def mytwitch(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    twitch_username = twitch_links.get(user_id)
    if twitch_username:
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Linked Twitch",
            description=f"🎮 Your linked Twitch username is:\n**{twitch_username}**",
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            "❌ You haven't linked a Twitch username yet. Use `/addtwitch` to link one!",
            ephemeral=True
        )


@tree.command(name="prestige", description="Reset your level and start prestige")
@app_commands.describe(confirm="Set to true to confirm prestige")
async def prestige(interaction: discord.Interaction, confirm: bool = False):
    user_id = str(interaction.user.id)
    data = user_data.get(user_id)
    if not data or data.get("level", 1) < MAX_LEVEL:
        await interaction.response.send_message(
            "❌ You need to be at max level (100) to prestige.",
            ephemeral=True
        )
        return

    if not confirm:
        await interaction.response.send_message(
            "⚠️ This will reset your level and XP but give you a prestige point.\n"
            "Run `/prestige confirm:true` to confirm.",
            ephemeral=True
        )
        return

    add_prestige(interaction.user.id)
    save_json(USERS_FILE, user_data)
    await interaction.response.send_message(
        f"🎉 {interaction.user.mention} has **prestiged**! Your level and XP have been reset.",
        ephemeral=True
    )
    logger.info(f"User {interaction.user} prestiged.")


@tree.command(name="resetuserdata", description="Reset XP and level for a user (admin only)")
@app_commands.describe(member="Member to reset")
async def resetuserdata(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return
    user_data.pop(str(member.id), None)
    save_json(USERS_FILE, user_data)
    await interaction.response.send_message(
        f"✅ Reset XP and level data for {member.display_name}.",
        ephemeral=True
    )
    logger.info(f"Admin {interaction.user} reset data for {member}")



@tree.command(name="setbirthday", description="Set your birthday (YYYY-MM-DD)")
@app_commands.describe(date="Your birthday in YYYY-MM-DD format")
async def setbirthday(interaction: discord.Interaction, date: str):
    try:
        # basic validation
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return await interaction.response.send_message(
            "❌ Invalid date format. Use YYYY-MM-DD.",
            ephemeral=True
        )
    uid = str(interaction.user.id)
    birthdays[uid] = date
    save_json(BIRTHDAYS_FILE, birthdays)
    await interaction.response.send_message(
        f"✅ Your birthday has been set to **{date}**.",
        ephemeral=True
    )


@tree.command(name="mybirthday", description="Show your saved birthday")
async def mybirthday(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    bday = birthdays.get(uid)
    if not bday:
        return await interaction.response.send_message(
            "❌ You have not set a birthday yet. Use /setbirthday.",
            ephemeral=True
        )
    await interaction.response.send_message(
        f"🎂 Your saved birthday is **{bday}**.",
        ephemeral=True
    )


@tree.command(name="rank", description="Show your current level and prestige")
async def rank(interaction: discord.Interaction):
    data = user_data.get(str(interaction.user.id), {"xp": 0, "level": 1, "prestige": 0})
    emoji = get_emoji_for_level(data["level"])
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Rank",
        color=discord.Color.gold()
    )
    embed.add_field(name="Level", value=f"{data['level']} {emoji}")
    embed.add_field(name="XP", value=f"{data['xp']} / {get_level_xp(data['level'])}")
    embed.add_field(name="Prestige", value=str(data["prestige"]))
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="leaderboard", description="Show top 10 ranked members")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(
        user_data.items(),
        key=lambda x: (x[1].get("prestige", 0), x[1].get("level", 0), x[1].get("xp", 0)),
        reverse=True
    )
    embed = discord.Embed(title="🏆 Top 10 Players", color=discord.Color.purple())
    count = 0
    for user_id, data in sorted_users:
        if count >= 10:
            break
        member = interaction.guild.get_member(int(user_id))
        if member:
            emoji = get_emoji_for_level(data["level"])
            embed.add_field(
                name=f"{count+1}. {member.display_name}",
                value=f"Level {data['level']} {emoji} | Prestige {data['prestige']}",
                inline=False
            )
            count += 1
    if count == 0:
        embed.description = "No data available."
    await interaction.response.send_message(embed=embed, ephemeral=True)



@tree.command(name="xp", description="Show your XP stats")
async def xp_command(interaction: discord.Interaction):
    data = get_user_record(interaction.user.id)
    emoji = get_emoji_for_level(data["level"])
    await interaction.response.send_message(
        f"XP: **{data['xp']}** | Level: **{data['level']}** {emoji} | Prestige: **{data['prestige']}**",
        ephemeral=True
    )

@tree.command(name="admin", description="Open CROBOT admin controls")
async def admin(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only!", ephemeral=True)

    embed = discord.Embed(
        title="🛠 CROBOT Admin Control Panel",
        description="Use the buttons below to view stats, reset levels, or force-save data.",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=AdminPanel(), ephemeral=True)



@tree.command(name="synccommands", description="Force sync CROBOT slash commands (admin only).")
async def synccommands(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You need admin permissions for this.", ephemeral=True
        )

    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild_obj)

        await tree.sync()

        await interaction.response.send_message(
            "✅ Slash commands synced. Global commands may take up to 1 hour to appear.",
            ephemeral=True
        )
        logger.info(f"Slash commands manually synced by {interaction.user}.")
    except Exception as e:
        await interaction.response.send_message("❌ Failed to sync commands.", ephemeral=True)
        logger.error(f"Manual command sync error: {e}")


# =========================
# ADMIN CONFIG COMMANDS (per-server channels & roles)
# =========================

@tree.command(name="setwelcomedm", description="Set the DM welcome message for this server (admin only)")
@app_commands.describe(message="Welcome DM text. Use {user} and {server} placeholders.")
async def setwelcomedm(interaction: discord.Interaction, message: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    set_guild_value(interaction.guild, "welcome_dm_message", message)
    await interaction.response.send_message(
        "✅ Welcome DM message updated for this server.",
        ephemeral=True
    )


@tree.command(name="setwelcome", description="Set this server's welcome channel (admin only)")
@app_commands.describe(channel="Channel to send welcome messages in")
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    set_guild_value(interaction.guild, "welcome_channel_id", channel.id)
    await interaction.response.send_message(
        f"✅ Welcome channel set to {channel.mention} for this server.",
        ephemeral=True
    )


@tree.command(name="setmemes", description="Set this server's meme channel (admin only)")
@app_commands.describe(channel="Channel to auto-post memes in")
async def setmemes(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    set_guild_value(interaction.guild, "meme_channel_id", channel.id)
    await interaction.response.send_message(
        f"✅ Meme channel set to {channel.mention} for this server.",
        ephemeral=True
    )



@tree.command(name="setmemeinterval", description="Set how often CROBOT posts memes in this server (admin only)")
@app_commands.describe(interval="How often memes should be posted")
@app_commands.choices(interval=[
    app_commands.Choice(name="Every 2 hours", value="2h"),
    app_commands.Choice(name="Every 6 hours", value="6h"),
    app_commands.Choice(name="Every 12 hours", value="12h"),
    app_commands.Choice(name="Every 48 hours", value="48h"),
    app_commands.Choice(name="Once a week", value="1w"),
])
async def setmemeinterval(interaction: discord.Interaction, interval: app_commands.Choice[str]):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)

    mapping = {
        "2h": 2 * 60 * 60,
        "6h": 6 * 60 * 60,
        "12h": 12 * 60 * 60,
        "48h": 48 * 60 * 60,
        "1w": 7 * 24 * 60 * 60,
    }
    seconds = mapping.get(interval.value, MEME_POST_INTERVAL)

    gid = str(interaction.guild.id)
    raw_cfg = guild_config.get(gid, {})
    raw_cfg["meme_interval"] = seconds
    # force next meme to be scheduled from now
    raw_cfg["next_meme_time"] = 0
    guild_config[gid] = raw_cfg
    save_json(GUILD_FILE, guild_config)

    await interaction.response.send_message(
        f"✅ Meme interval set to **{interval.name}** for this server.",
        ephemeral=True
    )




@tree.command(name="settwitch", description="Set this server's Twitch announcement channel (admin only)")
@app_commands.describe(channel="Channel to announce Twitch go-lives in")
async def settwitch(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    set_guild_value(interaction.guild, "twitch_channel_id", channel.id)
    await interaction.response.send_message(
        f"✅ Twitch live announcements will go to {channel.mention} for this server.",
        ephemeral=True
    )


@tree.command(name="setautorole", description="Set this server's auto-role for new members (admin only)")
@app_commands.describe(role="Role to give to new members automatically")
async def setautorole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    set_guild_value(interaction.guild, "auto_role_id", role.id)
    await interaction.response.send_message(
        f"✅ Auto-role set to {role.mention} for new members in this server.",
        ephemeral=True
    )




@tree.command(name="addwatchword", description="Add a word or phrase for CROBOT to watch for (admin only)")
@app_commands.describe(phrase="Word or phrase to watch for")
async def addwatchword(interaction: discord.Interaction, phrase: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    add_bad_word(interaction.guild, phrase)
    await interaction.response.send_message(
        f"✅ Added watch phrase: `{phrase}`",
        ephemeral=True
    )


@tree.command(name="removewatchword", description="Remove a watched word or phrase (admin only)")
@app_commands.describe(phrase="Word or phrase to remove")
async def removewatchword(interaction: discord.Interaction, phrase: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    remove_bad_word(interaction.guild, phrase)
    await interaction.response.send_message(
        f"✅ Removed watch phrase: `{phrase}` (if it existed).",
        ephemeral=True
    )


@tree.command(name="listwatchwords", description="List all watched words/phrases for this server")
async def listwatchwords(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    words = get_bad_words(interaction.guild)
    if not words:
        return await interaction.response.send_message(
            "ℹ No watchwords are configured for this server.",
            ephemeral=True
        )
    embed = discord.Embed(
        title="👁 Watchwords for this server",
        description="These words/phrases will trigger warnings:",
        color=discord.Color.orange()
    )
    embed.add_field(
        name="Watchwords",
        value=", ".join(f"`{w}`" for w in words),
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="setmodrole", description="Set which role CROBOT pings on moderation escalations (admin only)")
@app_commands.describe(role="Role to ping when someone hits 3+ warnings")
async def setmodrole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    set_guild_value(interaction.guild, "mod_role_id", role.id)
    await interaction.response.send_message(
        f"✅ Moderation escalation role set to {role.mention}.",
        ephemeral=True
    )


@tree.command(name="resetwarnings", description="Reset moderation warnings for a user (admin only)")
@app_commands.describe(member="Member whose warnings should be cleared")
async def resetwarnings(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    reset_warnings(interaction.guild.id, member.id)
    await interaction.response.send_message(
        f"✅ Warnings reset for {member.mention}.",
        ephemeral=True
    )



# =========================
# SLASH COMMANDS – FINDPLAYERS & MINIGAMES & FUN
# =========================

@tree.command(name="findplayers", description="Find and gather players for a game")
@app_commands.describe(game="Name of the game")
async def findplayers(interaction: discord.Interaction, game: str):
    embed = discord.Embed(
        title=f"Looking for players for **{game}**!",
        description=f"{interaction.user.mention} wants to play **{game}**!\n"
                    f"React with ✅ to join!\n\nConfirmations: 0",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")

    findplayers_sessions[msg.id] = {
        "game": game,
        "author": interaction.user,
        "confirmed": set()
    }

    async def auto_delete():
        await asyncio.sleep(90 * 60)  # 1 hour 30 minutes
        try:
            await msg.delete()
            findplayers_sessions.pop(msg.id, None)
            logger.info(f"Deleted findplayers session message {msg.id}")
        except Exception:
            pass

    bot.loop.create_task(auto_delete())
    await interaction.response.send_message(
        f"✅ Game session created for **{game}**!",
        ephemeral=True
    )


@tree.command(name="coinflip", description="Flip a coin, win XP if you guess right!")
@app_commands.describe(guess="Heads or tails?")
async def coinflip(interaction: discord.Interaction, guess: str):
    guess = guess.lower()
    if guess not in ["heads", "tails"]:
        await interaction.response.send_message(
            "❌ Please guess `heads` or `tails`.",
            ephemeral=True
        )
        return
    result = random.choice(["heads", "tails"])
    if guess == result:
        leveled_up, new_level = add_xp(interaction.user.id, 10)
        save_json(USERS_FILE, user_data)
        msg = f"🎉 You guessed correctly! It was **{result}**. You earned 10 XP!"
        if leveled_up:
            emoji = get_emoji_for_level(new_level)
            msg += f" You leveled up to **Level {new_level}**! {emoji}"
    else:
        msg = f"❌ Sorry, it was **{result}**. Better luck next time!"
    await interaction.response.send_message(msg, ephemeral=True)


@tree.command(name="trivia", description="Answer a trivia question and earn XP!")
async def trivia(interaction: discord.Interaction):
    question = random.choice(TRIVIA_QUESTIONS)

    # Public question in the channel
    await interaction.response.send_message(
        f"❓ **Trivia time!**\n**Question for {interaction.user.mention}:** {question['q']}\n"
        f"Type your answer in this channel within **30 seconds**!"
    )

    def check(m: discord.Message):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await interaction.channel.send(f"⏰ {interaction.user.mention} Time's up! No answer received.")
        return

    if question['a'].lower() in msg.content.lower():
        leveled_up, new_level = add_xp(interaction.user.id, 15)
        save_json(USERS_FILE, user_data)
        reply = f"🎉 {interaction.user.mention} Correct! You earned **15 XP**."
        if leveled_up:
            emoji = get_emoji_for_level(new_level)
            reply += f" You leveled up to **Level {new_level}**! {emoji}"
    else:
        reply = (
            f"❌ {interaction.user.mention} Incorrect! "
            f"The right answer was **{question['a']}**."
        )

    await interaction.channel.send(reply)


@tree.command(name="playradio", description="Play a preset radio station in your current voice channel")
@app_commands.choices(
    station=[
        app_commands.Choice(name="Lofi Chill", value="lofi"),
        app_commands.Choice(name="Chillhop Beats", value="chillhop"),
        app_commands.Choice(name="Phonk Radio", value="phonk"),
        app_commands.Choice(name="EDM Hits", value="edm"),
        app_commands.Choice(name="Synthwave FM", value="synthwave"),
    ]
)
async def playradio(interaction: discord.Interaction, station: app_commands.Choice[str]):
    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message(
            "❌ You must be in a voice channel to use this.",
            ephemeral=True
        )

    channel = interaction.user.voice.channel

    vc = interaction.guild.voice_client
    if vc and vc.is_connected():
        await vc.move_to(channel)
    else:
        vc = await channel.connect()

    preset = RADIO_STATIONS.get(station.value)
    if not preset:
        return await interaction.response.send_message(
            "❌ Unknown station. Please pick one of the presets.",
            ephemeral=True
        )

    url = preset["url"]
    name = preset["name"]

    try:
        source = discord.FFmpegOpusAudio(url)
        vc.stop()
        vc.play(source)
        await interaction.response.send_message(
            f"🎧 Playing **{name}** in {channel.mention}.",
            ephemeral=True
        )
        logger.info(f"Started radio station '{name}' in guild {interaction.guild.id}: {url}")
    except Exception as e:
        logger.error(f"Failed to play radio: {e}")
        await interaction.response.send_message(
            "❌ Failed to start radio. Voice dependencies or stream URL may be invalid.",
            ephemeral=True
        )


@tree.command(name="stopradio", description="Stop radio and disconnect from voice")
async def stopradio(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        return await interaction.response.send_message(
            "❌ I'm not in a voice channel.",
            ephemeral=True
        )

    try:
        await vc.disconnect()
        await interaction.response.send_message("⏹️ Radio stopped and disconnected.", ephemeral=True)
        logger.info(f"Stopped radio in guild {interaction.guild.id}")
    except Exception as e:
        logger.error(f"Failed to disconnect from voice: {e}")
        await interaction.response.send_message("❌ Failed to disconnect from voice.", ephemeral=True)


@tree.command(name="askcrobot", description="Ask CROBOT for advice or an opinion.")
async def askcrobot(interaction: discord.Interaction, *, question: str):
    responses = [
        "Short answer: {summary}. Long answer: you already knew that.",
        "Honestly? {summary}. Also drink some water.",
        "My advanced analysis says: {summary}.",
        "Based on 0% emotion and 100% chaos energy: {summary}.",
    ]

    lower_q = question.lower()
    if "stream" in lower_q:
        summary = "stay consistent and tweak your schedule"
    elif "discord" in lower_q or "server" in lower_q:
        summary = "clean channels, clear rules, and fun events grow a server"
    elif "content" in lower_q or "videos" in lower_q:
        summary = "improve one thing each video instead of everything at once"
    else:
        summary = "do the thing that scares you just a little bit"

    reply = random.choice(responses).format(summary=summary)
    await interaction.response.send_message(reply, ephemeral=False)



@tree.command(name="love", description="Spread love and positivity in the server 💖")
async def love(interaction: discord.Interaction):
    messages = [
        "💖 You are loved, valued, and welcome here.",
        "🌟 This server wouldn't be the same without you.",
        "🔥 You're important, you're seen, and we're glad you're here.",
        "👑 You matter — and we're grateful you’re part of Crooks & Castles!",
        "🌙 Even on hard days, you’re never alone. We appreciate you!"
    ]
    msg = random.choice(messages)
    await interaction.response.send_message(f"{interaction.user.mention} {msg}")


# =========================
# RUN THE BOT
# =========================

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
