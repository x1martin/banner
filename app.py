import os
from io import BytesIO
from functools import lru_cache
import requests
from flask import Flask, send_file, jsonify, request

app = Flask(__name__)

# HTTP Keep-Alive সেশন (এটি কানেকশন স্পিড অনেক বাড়িয়ে দেয়)
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

# প্লেয়ার ডেটা ক্যাশ করার জন্য (একই প্লেয়ারের ডেটা ৫ মিনিটের জন্য মেমোরিতে সেভ থাকবে)
@lru_cache(maxsize=1024)
def fetch_player_data(uid_or_name):
    url = (
        f"https://info.killersharmabot.online/player-info?uid={uid_or_name}"
        if uid_or_name.isdigit()
        else f"https://info.killersharmabot.online/player-info?name={uid_or_name}"
    )
    
    try:
        # ৫ সেকেন্ডের টাইমআউট দেওয়া হয়েছে যেন সার্ভার হ্যাং না হয়
        r = session.get(url, timeout=5)
        if r.status_code != 200:
            return None

        data = r.json()
        if not data.get("basicInfo"):
            return None
        return data
    except requests.RequestException:
        return None


# ব্যানার ইমেজ ক্যাশ করার জন্য (একই ইমেজ বারবার জেনারেট না করে মেমোরি থেকে ইনস্ট্যান্ট দেবে)
@lru_cache(maxsize=512)
def fetch_banner_image_cached(head_pic, banner_id, nickname, level, clan_name, pin_id, celebrity_status, prime_level, frame):
    url = (
        "https://image.killersharmabot.online/banner-image?"
        f"headPic={head_pic}"
        f"&bannerId={banner_id}"
        f"&name={nickname}"
        f"&level={level}"
        f"&guild={clan_name}"
        f"&pinId={pin_id}"
        f"&celebrity={celebrity_status}"
        f"&primeLevel={prime_level}"
        f"&frame={frame}"
    )
    
    try:
        r = session.get(url, timeout=5)
        r.raise_for_status()
        return r.content
    except requests.RequestException:
        return None


@app.route("/banner-image", methods=["GET"])
def banner_image():
    uid = request.args.get("uid")
    name = request.args.get("name")

    search = uid if uid else name

    if not search:
        return jsonify({"error": "Missing uid or name"}), 400

    # ক্যাশড ফাংশন থেকে প্লেয়ার ডেটা আনবে (খুবই ফাস্ট)
    player = fetch_player_data(search)

    if not player:
        return jsonify({"error": "Player not found"}), 404

    basic = player.get("basicInfo", {})
    clan = player.get("clanBasicInfo", {})

    prime_level = basic.get("primeLevel", {}).get("level", 0)
    frame = "true" if prime_level == 8 else "false"

    nickname = basic.get("nickname", "").replace("#", "%23").replace("&", "%26")
    clan_name = clan.get("clanName", "").replace("#", "%23").replace("&", "%26")

    # ক্যাশড ইমেজ ফাংশন কল (যদি আগে কেউ এই প্লেয়ারের ইমেজ চেয়ে থাকে, তবে ০ সেকেন্ডে লোড হবে)
    img = fetch_banner_image_cached(
        basic.get('headPic', ''),
        basic.get('bannerId', ''),
        nickname,
        basic.get('level', 2),
        clan_name,
        basic.get('pinId', '900000012'),
        basic.get('celebrityStatus', 0),
        prime_level,
        frame
    )

    if not img:
        return jsonify({"error": "Failed to generate banner image"}), 500

    # ব্রাউজার ক্যাশিং হেডার যুক্ত করা হয়েছে যাতে ইউজারের ব্রাউজারও ইমেজটি ১ দিন সেভ রাখে
    response = send_file(BytesIO(img), mimetype="image/png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


if __name__ == "__main__":
    # Render বা VPS এ চালানোর জন্য ডাইনামিক পোর্ট সাপোর্ট দেওয়া হয়েছে
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
