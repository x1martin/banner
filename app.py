import os
from io import BytesIO
import requests
from flask import Flask, send_file, jsonify, request
from cachetools import TTLCache

app = Flask(__name__)

# গ্লোবাল সেশন (Keep-Alive এনাবল করবে, যার ফলে স্পিড ৩ গুণ বেড়ে যাবে)
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

# ৫ মিনিটের জন্য প্লেয়ার ডেটা মেমোরিতে ক্যাশ থাকবে (সর্বোচ্চ ১০০০ জন প্লেয়ার)
player_cache = TTLCache(maxsize=1000, ttl=300)

# ১০ মিনিটের জন্য ব্যানার ইমেজ মেমোরিতে ক্যাশ থাকবে (সর্বোচ্চ ৫০০টি ইমেজ)
image_cache = TTLCache(maxsize=500, ttl=600)

def fetch_player_data(uid_or_name):
    if uid_or_name in player_cache:
        return player_cache[uid_or_name]

    url = (
        f"https://info.killersharmabot.online/player-info?uid={uid_or_name}"
        if uid_or_name.isdigit()
        else f"https://info.killersharmabot.online/player-info?name={uid_or_name}"
    )
    
    try:
        r = session.get(url, timeout=4)
        if r.status_code != 200:
            return None

        data = r.json()
        if not data.get("basicInfo"):
            return None
            
        player_cache[uid_or_name] = data
        return data
    except Exception:
        return None

def fetch_banner_image(player_data):
    basic = player_data.get("basicInfo", {})
    clan = player_data.get("clanBasicInfo", {})

    prime_level = basic.get("primeLevel", {}).get("level", 0)
    frame = "true" if prime_level == 8 else "false"

    nickname = basic.get("nickname", "").replace("#", "%23").replace("&", "%26")
    clan_name = clan.get("clanName", "").replace("#", "%23").replace("&", "%26")

    cache_key = f"{basic.get('headPic','')}_{basic.get('bannerId','')}_{nickname}_{clan_name}_{prime_level}"
    
    if cache_key in image_cache:
        return image_cache[cache_key]

    url = (
        "https://image.killersharmabot.online/banner-image?"
        f"headPic={basic.get('headPic','')}"
        f"&bannerId={basic.get('bannerId','')}"
        f"&name={nickname}"
        f"&level={basic.get('level',2)}"
        f"&guild={clan_name}"
        f"&pinId={basic.get('pinId','900000012')}"
        f"&celebrity={basic.get('celebrityStatus',0)}"
        f"&primeLevel={prime_level}"
        f"&frame={frame}"
    )

    try:
        r = session.get(url, timeout=5)
        if r.status_code == 200:
            img_content = r.content
            image_cache[cache_key] = img_content
            return img_content
    except Exception:
        pass
    return None

@app.route("/banner-image", methods=["GET"])
def banner_image():
    uid = request.args.get("uid")
    name = request.args.get("name")
    search = uid if uid else name

    if not search:
        return jsonify({"error": "Missing uid or name"}), 400

    player = fetch_player_data(search)
    if not player:
        return jsonify({"error": "Player not found"}), 404

    img = fetch_banner_image(player)
    if not img:
        return jsonify({"error": "Failed to generate banner"}), 500

    response = send_file(BytesIO(img), mimetype="image/png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
