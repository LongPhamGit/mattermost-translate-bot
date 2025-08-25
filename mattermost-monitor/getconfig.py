import requests
import json
import urllib3
import os

# Bỏ cảnh báo SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = "config.json"

# ========== Đọc config ==========
if not os.path.exists(CONFIG_FILE):
    print(f"❌ Không tìm thấy {CONFIG_FILE}")
    exit(1)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

SERVER_URL = CONFIG.get("SERVER_URL")
MMAUTHTOKEN = CONFIG.get("MMAUTHTOKEN")
MMUSERID = CONFIG.get("MMUSERID")

HEADERS = {
    "Authorization": f"Bearer {MMAUTHTOKEN}",
    "Content-Type": "application/json",
}
if MMUSERID:
    HEADERS["X-User-Id"] = MMUSERID


# ========== API ==========
def fetch_teams():
    url = f"{SERVER_URL}/api/v4/users/me/teams"
    resp = requests.get(url, headers=HEADERS, verify=False)
    resp.raise_for_status()
    return resp.json()

def fetch_channels(team_id):
    url = f"{SERVER_URL}/api/v4/users/me/teams/{team_id}/channels"
    resp = requests.get(url, headers=HEADERS, verify=False)
    resp.raise_for_status()
    return resp.json()


# ========== Main ==========
def main():
    teams = fetch_teams()
    all_channels = []

    print("📌 Danh sách team / channel bạn có quyền truy cập:")
    for team in teams:
        team_name = team["display_name"]
        team_id = team["id"]
        channels = fetch_channels(team_id)

        print(f"\n=== Team: {team_name} ===")
        for idx, ch in enumerate(channels, start=1):
            print(f"{idx:2d}. {ch['display_name']}  (ID: {ch['id']})")
            all_channels.append({
                "team": team_name,
                "id": ch["id"],
                "name": ch["display_name"]
            })

    # Hỏi user chọn
    choices = input("\n👉 Nhập số kênh muốn WATCH (cách nhau bằng dấu phẩy, ví dụ: 1,3,5): ")
    selected_ids = []
    selected_comments = {}

    if choices.strip():
        for c in choices.split(","):
            try:
                idx = int(c.strip()) - 1
                if 0 <= idx < len(all_channels):
                    ch = all_channels[idx]
                    selected_ids.append(ch["id"])
                    selected_comments[ch["id"]] = f"{ch['team']} / {ch['name']}"
            except ValueError:
                pass

    # Update config
    CONFIG["WATCH_CHANNELS"] = selected_ids
    CONFIG["_comment"] = selected_comments

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Đã cập nhật {CONFIG_FILE}")
    print("WATCH_CHANNELS =", selected_ids)
    print("_comment =", selected_comments)


if __name__ == "__main__":
    main()
