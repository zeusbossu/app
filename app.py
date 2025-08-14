import json
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, request, jsonify
from threading import Thread

# === Variabile direct în cod ===
BOT_TOKEN = "MTM3ODEyNTg2MTQ0NTgyODYxOA.G6nVFy.3lzPJPDK-awDNL0C82X0uLmvTxpZippp-pEfJQ"
SECRET_KEY = "0If6x7bvlUfh6GPpLvIALQLOlClaPaHH"
LOG_CHANNEL_ID = 1363927051375214754
ADMIN_ROLE_IDS = [987654321098765432]
PORT = 5000

# === Flask App ===
app = Flask(__name__)
app.secret_key = SECRET_KEY

DATA_FILE = "game_data.json"

# === Funcții pentru baza de date ===
def load_db():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                for key in ["players", "discords", "game_to_discord_id", "permitted_users"]:
                    data.setdefault(key, {})
                return data
        else:
            data = {"players": {}, "discords": {}, "game_to_discord_id": {}, "permitted_users": {}}
            save_db(data)
            return data
    except Exception as e:
        print(f"[ERROR] Eroare la încărcarea JSON: {e}")
        data = {"players": {}, "discords": {}, "game_to_discord_id": {}, "permitted_users": {}}
        save_db(data)
        return data

def save_db(db):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Eroare la salvarea JSON: {e}")

db = load_db()

# === Discord Bot ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def send_log(msg):
    await bot.wait_until_ready()
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(msg)
    else:
        print(f"[WARN] Canalul de log {LOG_CHANNEL_ID} nu a fost găsit")

@bot.event
async def on_ready():
    print(f"[BOT] Conectat ca {bot.user}")
    try:
        await bot.tree.sync()
        print("[BOT] Slash commands sincronizate")
        await send_log(f"Bot pornit ca {bot.user}")
    except Exception as e:
        print(f"[ERROR] Eroare la sincronizarea comenzilor: {e}")
        await send_log(f"Eroare la sincronizarea comenzilor: {e}")

@bot.tree.command(name="username", description="Schimbă nickname-ul unui jucător")
@app_commands.describe(nome="Numele actual", novonome="Noul nume")
async def username(interaction: discord.Interaction, nome: str, novonome: str):
    if not (any(role.id in ADMIN_ROLE_IDS for role in interaction.user.roles) or
            interaction.user.guild_permissions.administrator or
            str(interaction.user.id) in db["permitted_users"]):
        await interaction.response.send_message("Nu ai permisiunea pentru acest comandă", ephemeral=True)
        return

    discord_id = next((did for did, player_name in db["players"].items() if player_name == nome), None)

    if not discord_id or discord_id not in db["discords"]:
        await interaction.response.send_message(f"Jucătorul {nome} nu a fost găsit sau nu este legat de Discord", ephemeral=True)
        return

    if len(novonome) < 4 or len(novonome) > 200:
        await interaction.response.send_message("Numele trebuie să aibă între 4 și 200 de caractere", ephemeral=True)
        return

    db["players"][discord_id] = novonome
    save_db(db)
    game_id = next((gid for gid, did in db["game_to_discord_id"].items() if did == discord_id), "Necunoscut")
    await interaction.response.send_message(f"Numele pentru Game ID {game_id} a fost schimbat în {novonome}", ephemeral=True)
    await send_log(f"Nume schimbat: Game ID {game_id} Discord ID {discord_id} -> {novonome}")

# === Flask Routes ===
@app.route("/ping")
def ping():
    return jsonify({"status": "online"}), 200

@app.route("/get_username", methods=["GET"])
def get_username():
    game_id = request.args.get("id")
    if not game_id:
        return jsonify({"error": "Missing id"}), 400
    discord_id = db["game_to_discord_id"].get(str(game_id))
    if not discord_id or discord_id not in db["players"]:
        return jsonify({"new_username": f"Guest_{game_id}"}), 200
    return jsonify({"new_username": db["players"][discord_id]}), 200

@app.route("/get_wins", methods=["GET"])
def get_wins():
    game_id = request.args.get("id")
    if not game_id:
        return jsonify({"error": "Missing id"}), 400
    wins = db.get("wins", {}).get(str(game_id), 0)
    return jsonify({"wins": wins}), 200

@app.route("/check_auth", methods=["GET"])
def check_auth():
    game_id = request.args.get("id")
    if not game_id:
        return jsonify({"error": "Missing id"}), 400
    auth = str(game_id) in db["game_to_discord_id"]
    return jsonify({"auth": auth, "message": "Autorizat" if auth else "Nu este autorizat"}), 200

@app.route("/player_join", methods=["POST"])
def player_join():
    data = request.get_json()
    game_id = str(data.get("id"))
    username = data.get("username")
    if not game_id or not username:
        return jsonify({"error": "Missing id or username"}), 400
    db["players"][game_id] = username
    save_db(db)
    print(f"[SERVER] Player joined: {username} (Game ID: {game_id})")
    return jsonify({"status": "ok"}), 200

@app.route("/player_leave", methods=["POST"])
def player_leave():
    data = request.get_json()
    game_id = str(data.get("id"))
    if not game_id:
        return jsonify({"error": "Missing id"}), 400
    db["players"].pop(game_id, None)
    save_db(db)
    print(f"[SERVER] Player left (Game ID: {game_id})")
    return jsonify({"status": "ok"}), 200

# === Pornire Flask ===
def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# === Main ===
if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("[INFO] Pornesc botul Discord...")
    bot.run(BOT_TOKEN)