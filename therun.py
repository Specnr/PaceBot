import discord
import twitch
from functools import cmp_to_key

def log(msg):
    print(f"[LOG]: {msg}")


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


def should_process_run(run, game, min_split, min_split_thold):
    # Require correct game
    if run["game"] != game:
        return False
    
    # Require correct SpeedrunIGT version
    valid = False
    for split in run["splits"]:
        if split["name"] == "Blind Travel":
            valid = True
    if not valid:
        log(f"{run['user']} is on invalid SpeedrunIGT version")
        return False
    
    invalidSplit = run["currentSplitIndex"] < min_split or run["splits"][min_split - 1]["splitTime"] is None
    if run["hasReset"] or invalidSplit or (min_split_thold != -1 and run["splits"][min_split - 1]["splitTime"] > min_split_thold):
        log(f"{run['user']} pace did not meet minimum requirements")
        return False
    
    return True


def ms_to_time(ms):
    if ms is None:
        return "0:00"
    total_s = ms / 1000
    m = int(total_s // 60)
    s = int(total_s % 60)
    pref = "0" if s < 10 else ""
    m_pref = "0" if m < 10 else ""
    return f"{m_pref}{m}:{pref}{s}"


async def get_run_embed(pace, settings):
    colour_idx = pace["currentSplitIndex"] - 1 if pace["currentSplitIndex"] - 1 >= 0 and pace["currentSplitIndex"] - 1 < len(settings["split-colours"]) else 0
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


def generate_sorted_pace(runners_dict):
    paces = []
    for pace in runners_dict.values():
        paces.append(pace)
    return sorted(paces, key=cmp_to_key(compare_pace))