import requests
import discord
import twitch
from functools import cmp_to_key

API = "https://therun.gg/api/live"


def log(msg):
    print(f"[LOG]: {msg}")


def validation(pace, settings, run_storage):
    min_split, only_live, min_split_thold = settings["minimum-split"], settings["only-show-live"], settings["minimum-split-threshold"]

    if pace["splits"][0]["name"] != "Enter Nether":
        log(f"{pace['user']} is not playing 1.16.1")
        return False
    
    found = False
    prev = None
    for split in pace["splits"]:
        if prev is None:
            prev = split
        else:
            # Ensure jank runs arent seen
            if prev["splitTime"] is not None and split["splitTime"] is not None and prev["splitTime"] > split["splitTime"]:
                return False
            if prev["splitTime"] is None and split["splitTime"] is not None:
                return False

        if split["name"] == "Blind Travel":
            found = True
    if not found:
        log(f"{pace['user']} is playing on outdated SpeedrunIGT")
        return False

    invalidSplit = pace["currentSplitIndex"] < min_split or pace["splits"][min_split - 1]["splitTime"] is None
    if pace["hasReset"] or invalidSplit or (min_split_thold != -1 and pace["splits"][min_split - 1]["splitTime"] > min_split_thold):
        log(f"{pace['user']} pace did not meet minimum requirements")
        return False
    if only_live and not pace["currentlyStreaming"]:
        log(f"{pace['user']} is not live")
        return False
    if pace["user"] in run_storage and pace["insertedAt"] != run_storage[pace["user"]]["insertedAt"] and pace["splits"] == run_storage[pace["user"]]["splits"]:
        log(f"{pace['user']}'s pace is a dupe and will be ignored")
        return False
    
    return True


def can_run_be_archived(pace):
    limits = [
        (2, 300000),
        (3, 420000),
        (4, 510000),
        (5, 540000),
        (6, 660000)
    ]

    for idx, limit in limits:
        if pace["splits"][idx]["splitTime"] is None:
            return -1
        if pace["splits"][idx]["splitTime"] < limit:
            return idx
    return -1

def simplify_pace(paces):
    return [{"user": p["user"], "currentSplitIndex": p["currentSplitIndex"]} for p in paces]


def get_storeable_run(pace):
    return {"insertedAt": pace["insertedAt"], "splits": pace["splits"]}


def get_split_idx(player):
    for i in range(len(player["splits"]) - 1, -1, -1):
        curr_split = player["splits"][i]["splitTime"]
        if curr_split != None:
            return i
    return -1


def compare_pace(p1, p2):
    # Get split levels
    p1_split_level, p2_split_level = get_split_idx(p1), get_split_idx(p2)
    p1_curr_split, p2_curr_split = p1["splits"][p1_split_level]["splitTime"], p2["splits"][p2_split_level]["splitTime"]
    if p1_split_level > p2_split_level:
        return 1
    if p2_split_level > p1_split_level:
        return -1
    # At the same split, prioritize player on better pace
    if p1_split_level == -1:    # Not in nether yet
        return 0
    if p1_curr_split > p2_curr_split:
        return -1
    if p2_curr_split > p1_curr_split:
        return 1
    return 0


def get_all_pace(game, settings, run_storage):
    while True:
        try:
            data = requests.get(API, timeout=30).json()
            break
        except requests.exceptions.Timeout:
            log("Request timed out, will try again...")
    filtered = list(filter(lambda x: x["game"] == game, data))
    raw_count = len(filtered)
    filtered = list(filter(lambda x: validation(x, settings, run_storage), filtered))
    return sorted(filtered, key=cmp_to_key(compare_pace)), raw_count


def ms_to_time(ms):
    if ms is None:
        return "0:00"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = int(total_s % 60)
    pref = "0" if s < 10 else ""
    m_pref = "0" if m < 10 else ""
    return f"{m_pref}{m}:{pref}{s}"


def get_archive_run_msg(pace):
    twitch_username = pace['user']
    pace_idx = can_run_be_archived(pace)
    best_split = pace['splits'][pace_idx]
    msg = f"**{twitch_username}**\n"
    msg += f"{best_split['name']} @ {ms_to_time(best_split['splitTime'])}\n>>> "
    for split in pace["splits"]:
        s_time, s_name = split["splitTime"], split["name"]
        if s_time is None:
            break
        msg += f"**{ms_to_time(s_time)}** {s_name}\n"
    return msg


async def get_run_embed(pace, settings):
    curr_split_idx = get_split_idx(pace)
    colour_idx = curr_split_idx if curr_split_idx >= 0 and curr_split_idx < len(settings["split-colours"]) else 0
    twitch_username = pace['user']
    embed_msg = discord.Embed(title=twitch_username,
                              url=f"https://twitch.tv/{twitch_username}" if pace["currentlyStreaming"] else None,
                              color=discord.Color.from_str(settings["split-colours"][colour_idx]))
    pfp_url = await twitch.get_pfp(twitch_username)
    embed_msg.set_thumbnail(url=pfp_url)
    embed_msg.set_footer(text=f"Current Time - {ms_to_time(pace['currentTime'])}")

    for split in pace["splits"]:
        s_time, s_name = split["splitTime"], split["name"]
        if s_time is None:
            break
        embed_msg.add_field(
            name=f"**{ms_to_time(s_time)}** {s_name}", value="", inline=False)

    return embed_msg
