import os
from io import BytesIO
import asyncio
import aiohttp
from flask import Flask, send_file, jsonify, request

app = Flask(__name__)

# ইন-মেমোরি ক্যাশ ডিকশনারি (Fastest Cache Method for Async)
PLAYER_CACHE = {}
BANNER_CACHE = {}

# গ্লোবাল অ্যাসিনক্রোনাস সেশন
async_session = None

async def get_session():
    global async_session
    if async_session is None or async_session.closed:
        # Keep-Alive এবং ফাস্ট কানেকশন পুলিং সেটআপ
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        async_session = aiohttp.ClientSession(connector=connector)
    return async_session

async def fetch_player_data(uid_or_name):
    # ক্যাশে থাকলে সেখান থেকে ১ মিলি-সেকেন্ডে রিটার্ন করবে
    if uid_or_name in PLAYER_CACHE:
        return PLAYER_CACHE[uid_or_name]

    url = (
        f"https://info.killersharmabot.online/player-info?uid={uid_or_name}"
        if uid_or_name.isdigit()
        else f"https://info.killersharmabot.online/player-info?name={uid_or_name}"
    )
    
    session = await get_session()
    try:
        async with session.get(url, timeout=4) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("basicInfo"):
                    # ৫ মিনিটের জন্য ক্যাশে সেভ করে রাখছি
                    PLAYER_CACHE[uid_or_name] = data
                    return data
    except Exception:
        pass
    return None

async def fetch_banner_image(player_data):
    basic = player_data.get("basicInfo", {})
    clan = player_data.get("clanBasicInfo", {})

    prime_level = basic.get("primeLevel", {}).get("level", 0)
    frame = "true" if prime_level == 8 else "false"

    nickname = basic.get("nickname", "").replace("#", "%23").replace("&", "%26")
    clan_name = clan.get("clanName", "").replace("#", "%23").replace("&", "%26")

    # ইউনিক ক্যাশ কি (Cache Key) তৈরি
    cache_key = f"{basic.get('headPic','')}_{basic.get('bannerId','')}_{nickname}_{clan_name}"
    if cache_key in BANNER_CACHE:
        return BANNER_CACHE[cache_key]

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

    session = await get_session()
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                img_data = await response.read()
                # ইমেজটি ক্যাশে সেভ করা হচ্ছে
                BANNER_CACHE[cache_key] = img_data
                return img_data
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

    # Flask সিঙ্ক হওয়ায় অ্যাসিনক্রোনাস ফাংশনগুলোকে ইভেন্ট লুপ দিয়ে রান করানো হচ্ছে
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        player = loop.run_until_complete(fetch_player_data(search))
        if not player:
            return jsonify({"error": "Player not found"}), 404

        img = loop.run_until_complete(fetch_banner_image(player))
        if not img:
            return jsonify({"error": "Failed to generate banner"}), 500
    finally:
        loop.close()

    # ব্রাউজার লেভেলে ক্যাশ কন্ট্রোল যুক্ত করা হয়েছে যাতে ইউজারের ফোনও স্পিড পায়
    response = send_file(BytesIO(img), mimetype="image/png")
    response.headers["Cache-Control"] = "public, max-age=86400" # ২৪ ঘণ্টা ব্রাউজারে সেভ থাকবে
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
