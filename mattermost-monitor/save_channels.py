import requests
import json

# ===== Load config hiện tại =====
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL = config.get("SERVER_URL")
MMUSERID = config.get("MMUSERID")
MMAUTHTOKEN = config.get("MMAUTHTOKEN")

cookies = {
    "MMUSERID": MMUSERID,
    "MMAUTHTOKEN": MMAUTHTOKEN
}

# ===== Lấy danh sách team mà user tham gia =====
team_resp = requests.get(f"{SERVER_URL}/api/v4/users/me/teams", cookies=cookies)
team_resp.raise_for_status()
teams = team_resp.json()

all_channel_ids = []
comments = {}

for t in teams:
    team_id = t["id"]

    # Lấy tất cả channel mà user tham gia trong team
    ch_resp = requests.get(f"{SERVER_URL}/api/v4/users/me/teams/{team_id}/channels", cookies=cookies)
    ch_resp.raise_for_status()
    channels = ch_resp.json()
    for ch in channels:
        ch_id = ch["id"]
        ch_name = ch["name"]
        all_channel_ids.append(ch_id)
        comments[ch_id] = ch_name

# ===== Cập nhật config.json =====
config["WATCH_CHANNELS"] = all_channel_ids
config["_comment"] = comments

with open("config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print(f"Đã cập nhật WATCH_CHANNELS với {len(all_channel_ids)} channel_id")
print("Danh sách channel_id và tên channel:")
for ch_id, ch_name in comments.items():
    print(f"{ch_name}: {ch_id}")
