import requests
from io import BytesIO
from flask import Flask, send_file, jsonify, request

app = Flask(__name__)

def fetch_player_data(uid_or_name):
    url = (
        f"https://info.killersharmabot.online/player-info?uid={uid_or_name}"
        if uid_or_name.isdigit()
        else f"https://info.killersharmabot.online/player-info?name={uid_or_name}"
    )

    r = requests.get(url)
    if r.status_code != 200:
        return None

    data = r.json()
    if not data.get("basicInfo"):
        return None

    return data


def fetch_banner_image(player_data):
    basic = player_data.get("basicInfo", {})
    clan = player_data.get("clanBasicInfo", {})

    prime_level = basic.get("primeLevel", {}).get("level", 0)
    frame = "true" if prime_level == 8 else "false"

    nickname = basic.get("nickname", "").replace("#", "%23").replace("&", "%26")
    clan_name = clan.get("clanName", "").replace("#", "%23").replace("&", "%26")

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

    r = requests.get(url)
    r.raise_for_status()
    return r.content


@app.route("/banner-image", methods=["GET"])
def banner_image():

    uid = request.args.get("uid")
    name = request.args.get("name")

    search = uid if uid else name

    if not search:
        return jsonify({
            "error": "Missing uid or name"
        }), 400

    player = fetch_player_data(search)

    if not player:
        return jsonify({
            "error": "Player not found"
        }), 404

    img = fetch_banner_image(player)

    return send_file(
        BytesIO(img),
        mimetype="image/png"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )