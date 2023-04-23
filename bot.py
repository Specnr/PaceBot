from datetime import datetime
import websockets
import discord
import asyncio
import json
import os

import therun

from dotenv import load_dotenv
load_dotenv()

client = discord.Client(intents=discord.Intents.default())
ACTIVE_RUNS = {}
HAVE_RUNS_CHANGES = True
TIME_SINCE_UPDATED = -1

settings = {}
with open("config.json") as f:
    settings = json.load(f)


@client.event
async def on_ready():
    print(f"Logged in as {client.user.name} (ID: {client.user.id})")

    
def log(msg):
    print(f"[LOG]: {msg}")


async def send_archive_msg(user):
    if settings["archive-channel-id"] == -1 or therun.can_run_be_archived(ACTIVE_RUNS[user]) == -1:
        return
    channel = client.get_channel(settings["archive-channel-id"])
    msg = therun.get_archive_run_msg(ACTIVE_RUNS[user])
    await channel.send(msg)
    log(f"Archiving pace from {user}")


async def wipe_old_pace():
    channel = client.get_channel(settings["output-channel-id"])
    await channel.purge(check=lambda m: m.author == client.user)


async def update_msgs():
    global HAVE_RUNS_CHANGES
    if not HAVE_RUNS_CHANGES:
        log("Skipping update since no changes were made")
        return
    
    log("Updating pace messages")
    HAVE_RUNS_CHANGES = False
    sorted_pace = therun.generate_sorted_pace(ACTIVE_RUNS)
    embeds = [await therun.get_run_embed(pace, settings) for pace in sorted_pace]

    channel = client.get_channel(settings["output-channel-id"])
    await wipe_old_pace()
    if len(sorted_pace) == 0:
        await channel.send(settings["no-pace-msg"])
        return
    for embed in embeds:
        await channel.send(embed=embed)


async def on_message(msg):
    global HAVE_RUNS_CHANGES
    msg_json = json.loads(msg)

    if not therun.should_process_run(msg_json["run"], settings["game"], settings["minimum-split"], settings["minimum-split-threshold"]):
        if msg_json["user"] in ACTIVE_RUNS:
            await send_archive_msg(msg_json["user"])
            log(f"Removing {msg_json['user']} pace from active")
            del ACTIVE_RUNS[msg_json["user"]]
            HAVE_RUNS_CHANGES = True
            return
        log(f"Discarding message from {msg_json['user']}")
        return
    
    log(f"Reading message from {msg_json['user']}")
    HAVE_RUNS_CHANGES = True
    # Update msg
    if msg_json["user"] in ACTIVE_RUNS:
        active_run = ACTIVE_RUNS[msg_json["user"]]
        # Remove msg
        if msg_json["run"]["splits"][0]["splitTime"] != active_run["splits"][0]["splitTime"]:
            await send_archive_msg(msg_json["user"])
            log(f"Removing {msg_json['user']} pace from active")
            del ACTIVE_RUNS[msg_json["user"]]
            return
        if msg_json["run"]["currentSplitIndex"] == active_run["currentSplitIndex"]:
            log(f"No split change in update from {msg_json['user']}")
            HAVE_RUNS_CHANGES = False

    ACTIVE_RUNS[msg_json["user"]] = msg_json["run"]


async def listen():
    global TIME_SINCE_UPDATED
    WS_ENDPOINT = "wss://fh76djw1t9.execute-api.eu-west-1.amazonaws.com/prod"
    await client.wait_until_ready()
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="World Record"))
    async with websockets.connect(WS_ENDPOINT) as ws:
        while True:
            msg = await ws.recv()
            await on_message(msg)
            if TIME_SINCE_UPDATED == -1 or (datetime.now() - TIME_SINCE_UPDATED).total_seconds() > settings["update-frequency"]:
                await update_msgs()
                TIME_SINCE_UPDATED = datetime.now()


async def start():
    print("Starting Discord client...")
    # Start the Discord client
    await client.start(os.getenv('DISCORD_SECRET'))


loop = asyncio.get_event_loop()
loop.create_task(start())
loop.create_task(listen())
loop.run_forever()