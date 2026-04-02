import json
import os
import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

HA_URL = os.environ.get("HA_URL", "http://supervisor/core")
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
print(f"SUPERVISOR_TOKEN presente: {bool(os.environ.get('SUPERVISOR_TOKEN'))}", flush=True)
print(f"Token in uso: {'SUPERVISOR' if os.environ.get('SUPERVISOR_TOKEN') else 'LONG-LIVED'}", flush=True)
DB_PATH = "/config/dispensa.db"

OPTIONS_PATH = "/data/options.json"
def get_options():
    try:
        with open(OPTIONS_PATH) as f:
            return json.load(f)
    except:
        return {"telegram_token": "", "telegram_chat_id": "", "giorni_alert_scadenza": 3, "soglia_scorte_minime": 1}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ean TEXT NOT NULL,
            nome TEXT NOT NULL,
            marca TEXT,
            categoria TEXT,
            immagine_url TEXT,
            quantita INTEGER DEFAULT 1,
            scadenza TEXT,
            data_inserimento TEXT DEFAULT (datetime('now')),
            note TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS barcode_cache (
            ean TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            marca TEXT,
            categoria TEXT,
            immagine_url TEXT,
            nutriscore TEXT,
            nutriments TEXT,
            data_inserimento TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS lista_spesa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            quantita INTEGER DEFAULT 1,
            ean TEXT,
            marca TEXT,
            completato INTEGER DEFAULT 0,
            data_aggiunta TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS storico_movimenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ean TEXT,
            nome TEXT NOT NULL,
            marca TEXT,
            categoria TEXT,
            tipo TEXT NOT NULL,
            quantita INTEGER DEFAULT 1,
            data TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    # Migrazione DB — aggiunge colonne se non esistono
    try:
        c.execute("ALTER TABLE prodotti ADD COLUMN nutriments TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE prodotti ADD COLUMN nutriscore TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE prodotti ADD COLUMN posizione TEXT DEFAULT 'Dispensa'")
    except:
        pass
    try:
        c.execute("ALTER TABLE barcode_cache ADD COLUMN nutriscore TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE barcode_cache ADD COLUMN nutriments TEXT")
    except:
        pass
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def aggiungi_a_lista_spesa(nome, ean="", marca=""):
    """Aggiunge un prodotto alla lista della spesa se non già presente e non completato"""
    conn = get_db()
    esistente = conn.execute(
        "SELECT id FROM lista_spesa WHERE ean = ? AND completato = 0",
        (ean,)
    ).fetchone()
    if not esistente:
        conn.execute("""
            INSERT INTO lista_spesa (nome, ean, marca)
            VALUES (?, ?, ?)
        """, (nome, ean, marca))
        conn.commit()
    conn.close()

def log_movimento(nome, tipo, ean="", marca="", categoria="", quantita=1):
    """Logga un movimento nel storico (acquisto, consumo, scaduto, eliminato)"""
    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO storico_movimenti (ean, nome, marca, categoria, tipo, quantita)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ean, nome, marca, categoria, tipo, quantita))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Errore log movimento: {e}")

def aggiorna_sensori_ha():
    conn = get_db()
    prodotti = conn.execute("SELECT * FROM prodotti ORDER BY scadenza ASC").fetchall()
    conn.close()

    oggi = datetime.now().date()
    opts = get_options()
    giorni_soglia = opts.get("giorni_alert_scadenza", 3)

    in_scadenza = []
    esauriti = []
    totale = len(prodotti)

    for p in prodotti:
        if p["quantita"] <= opts.get("soglia_scorte_minime", 1) - 1:
            esauriti.append(p["nome"])
            # Aggiunge automaticamente alla lista della spesa
            aggiungi_a_lista_spesa(p["nome"], p["ean"], p["marca"] or "")
        if p["scadenza"]:
            try:
                scad = datetime.strptime(p["scadenza"], "%Y-%m-%d").date()
                if (scad - oggi).days <= giorni_soglia:
                    in_scadenza.append({"nome": p["nome"], "scadenza": p["scadenza"], "giorni": (scad - oggi).days})
            except:
                pass

    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

    stati = {
        "sensor.dispensa_totale_prodotti": {
            "state": totale,
            "attributes": {"friendly_name": "Dispensa: prodotti totali", "icon": "mdi:package-variant"}
        },
        "sensor.dispensa_in_scadenza": {
            "state": len(in_scadenza),
            "attributes": {
                "friendly_name": "Dispensa: in scadenza",
                "prodotti": in_scadenza,
                "icon": "mdi:calendar-alert"
            }
        },
        "sensor.dispensa_esauriti": {
            "state": len(esauriti),
            "attributes": {
                "friendly_name": "Dispensa: esauriti",
                "prodotti": esauriti,
                "icon": "mdi:package-variant-remove"
            }
        }
    }

    for entity_id, payload in stati.items():
        try:
            requests.post(
                f"{HA_URL}/api/states/{entity_id}",
                headers=headers,
                json=payload,
                timeout=5
            )
        except Exception as e:
            print(f"Errore aggiornamento HA {entity_id}: {e}")

    if in_scadenza or esauriti:
        invia_notifica_telegram(in_scadenza, esauriti)

def invia_notifica_telegram(in_scadenza, esauriti):
    opts = get_options()
    token = opts.get("telegram_token", "")
    chat_id_raw = opts.get("telegram_chat_id", "")
    if not token or not chat_id_raw:
        return

    chat_ids = [c.strip() for c in str(chat_id_raw).split(",") if c.strip()]

    msg = "🛒 *Aggiornamento dispensa*\n\n"
    if in_scadenza:
        msg += "⚠️ *In scadenza:*\n"
        for p in in_scadenza:
            giorni = p["giorni"]
            if giorni < 0:
                label = "scaduto!"
            elif giorni == 0:
                label = "scade oggi!"
            elif giorni == 1:
                label = "scade domani"
            else:
                label = f"scade tra {giorni} giorni"
            msg += f"  • {p['nome']} — _{label}_\n"
        msg += "\n"
    if esauriti:
        msg += "❌ *Esauriti:*\n"
        for nome in esauriti:
            msg += f"  • {nome}\n"

    for chat_id in chat_ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print(f"Errore Telegram chat {chat_id}: {e}")

@app.route("/api/barcode/<ean>", methods=["GET"])
def cerca_barcode(ean):
    headers = {"User-Agent": "DispensaManager/1.0.1"}

    # 1. Controlla prima la cache locale
    conn = get_db()
    cached = conn.execute("SELECT * FROM barcode_cache WHERE ean = ?", (ean,)).fetchone()
    conn.close()
    if cached:
        nutriments_cached = None
        if cached["nutriments"]:
            try:
                nutriments_cached = json.loads(cached["nutriments"])
            except:
                nutriments_cached = None
        return jsonify({
            "trovato": True,
            "fonte": "cache_locale",
            "ean": ean,
            "nome": cached["nome"],
            "marca": cached["marca"] or "",
            "categoria": cached["categoria"] or "",
            "immagine_url": cached["immagine_url"] or "",
            "nutriscore": cached["nutriscore"] or "",
            "nutriments": nutriments_cached or {}
        })

    # 2. Cerca nei database online
    databases = [
        f"https://world.openfoodfacts.org/api/v2/product/{ean}.json",
        f"https://world.openproductsfacts.org/api/v2/product/{ean}.json",
        f"https://world.openbeautyfacts.org/api/v2/product/{ean}.json",
    ]
    for url in databases:
        try:
            r = requests.get(url, timeout=8, headers=headers)
            data = r.json()
            if data.get("status") == 1:
                p = data["product"]
                nutriments = p.get("nutriments", {})
                return jsonify({
                    "trovato": True,
                    "fonte": "online",
                    "ean": ean,
                    "nome": p.get("product_name_it") or p.get("product_name", "Prodotto sconosciuto"),
                    "marca": (p.get("brands", "").split(",")[0].strip()),
                    "categoria": p.get("categories_tags", [""])[0].replace("en:", "").replace("-", " ") if p.get("categories_tags") else "",
                    "immagine_url": p.get("image_front_small_url", ""),
                    "nutriscore": p.get("nutriscore_grade", "").upper(),
                    "nutriments": {
                        "energia_kcal": nutriments.get("energy-kcal_100g"),
                        "grassi": nutriments.get("fat_100g"),
                        "grassi_saturi": nutriments.get("saturated-fat_100g"),
                        "carboidrati": nutriments.get("carbohydrates_100g"),
                        "zuccheri": nutriments.get("sugars_100g"),
                        "fibre": nutriments.get("fiber_100g"),
                        "proteine": nutriments.get("proteins_100g"),
                        "sale": nutriments.get("salt_100g"),
                    }
                })
        except:
            continue

    return jsonify({"trovato": False, "ean": ean, "nome": "", "marca": "", "categoria": "", "immagine_url": "", "nutriscore": "", "nutriments": {}})

@app.route("/api/lista-spesa", methods=["GET"])
def get_lista_spesa():
    conn = get_db()
    items = conn.execute("SELECT * FROM lista_spesa ORDER BY completato ASC, data_aggiunta DESC").fetchall()
    conn.close()
    return jsonify([dict(i) for i in items])

@app.route("/api/lista-spesa", methods=["POST"])
def aggiungi_lista_spesa():
    data = request.json
    conn = get_db()
    conn.execute("""
        INSERT INTO lista_spesa (nome, quantita, ean, marca)
        VALUES (?, ?, ?, ?)
    """, (data.get("nome", ""), data.get("quantita", 1), data.get("ean", ""), data.get("marca", "")))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201

@app.route("/api/lista-spesa/<int:id>", methods=["PUT"])
def aggiorna_lista_spesa(id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE lista_spesa SET completato = ?, quantita = ? WHERE id = ?",
        (data.get("completato", 0), data.get("quantita", 1), id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/lista-spesa/<int:id>", methods=["DELETE"])
def elimina_lista_spesa(id):
    conn = get_db()
    conn.execute("DELETE FROM lista_spesa WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/lista-spesa/svuota-completati", methods=["DELETE"])
def svuota_completati():
    conn = get_db()
    conn.execute("DELETE FROM lista_spesa WHERE completato = 1")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/lista-spesa/invia-telegram", methods=["GET"])
def invia_lista_spesa_telegram():
    opts = get_options()
    token = opts.get("telegram_token", "")
    chat_id_raw = opts.get("telegram_chat_id", "")
    if not token or not chat_id_raw:
        return jsonify({"ok": False, "errore": "Telegram non configurato"})

    conn = get_db()
    items = conn.execute("SELECT * FROM lista_spesa WHERE completato = 0 ORDER BY data_aggiunta DESC").fetchall()
    conn.close()

    if not items:
        return jsonify({"ok": False, "errore": "Lista spesa vuota"})

    msg = f"🛒 *Lista della Spesa*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
    for item in items:
        msg += f"  ☐ {item['nome']}"
        if item['quantita'] > 1:
            msg += f" ×{item['quantita']}"
        if item['marca']:
            msg += f" _{item['marca']}_"
        msg += "\n"

    chat_ids = [c.strip() for c in str(chat_id_raw).split(",") if c.strip()]
    for cid in chat_ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print(f"Errore Telegram lista spesa {cid}: {e}")

    return jsonify({"ok": True, "totale": len(items)})

@app.route("/api/barcode-cache", methods=["POST"])
def salva_barcode_cache():
    data = request.json
    ean = data.get("ean", "")
    if not ean or ean.startswith("MANUAL-"):
        return jsonify({"ok": False, "errore": "EAN non valido"})
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO barcode_cache (ean, nome, marca, categoria, immagine_url, nutriscore, nutriments)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ean,
        data.get("nome", ""),
        data.get("marca", ""),
        data.get("categoria", ""),
        data.get("immagine_url", ""),
        data.get("nutriscore", ""),
        json.dumps(data.get("nutriments")) if data.get("nutriments") else None
    ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/prodotti", methods=["GET"])
def lista_prodotti():
    conn = get_db()
    prodotti = conn.execute("SELECT * FROM prodotti ORDER BY scadenza ASC NULLS LAST").fetchall()
    conn.close()
    oggi = datetime.now().date()
    result = []
    for p in prodotti:
        d = dict(p)
        if d["scadenza"]:
            try:
                scad = datetime.strptime(d["scadenza"], "%Y-%m-%d").date()
                d["giorni_alla_scadenza"] = (scad - oggi).days
            except:
                d["giorni_alla_scadenza"] = None
        else:
            d["giorni_alla_scadenza"] = None
        # Deserializza nutriments da JSON string
        if d.get("nutriments") and isinstance(d["nutriments"], str):
            try:
                d["nutriments"] = json.loads(d["nutriments"])
            except:
                d["nutriments"] = None
        result.append(d)
    return jsonify(result)

@app.route("/api/prodotti", methods=["POST"])
def aggiungi_prodotto():
    data = request.json
    conn = get_db()
    conn.execute("""
        INSERT INTO prodotti (ean, nome, marca, categoria, immagine_url, quantita, scadenza, note, nutriments, nutriscore)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("ean", ""),
        data.get("nome", "Prodotto"),
        data.get("marca", ""),
        data.get("categoria", ""),
        data.get("immagine_url", ""),
        data.get("quantita", 1),
        data.get("scadenza"),
        data.get("note", ""),
        json.dumps(data.get("nutriments")) if data.get("nutriments") else None,
        data.get("nutriscore", "")
    ))
    conn.commit()
    conn.close()
    log_movimento(
        nome=data.get("nome", "Prodotto"),
        tipo="acquisto",
        ean=data.get("ean", ""),
        marca=data.get("marca", ""),
        categoria=data.get("categoria", ""),
        quantita=data.get("quantita", 1)
    )
    aggiorna_sensori_ha()
    return jsonify({"ok": True}), 201

@app.route("/api/prodotti/<int:id>", methods=["PUT"])
def aggiorna_prodotto(id):
    data = request.json
    conn = get_db()
    # Leggi prodotto prima dell'aggiornamento per loggare
    p = conn.execute("SELECT * FROM prodotti WHERE id = ?", (id,)).fetchone()
    fields = []
    values = []
    for campo in ["nome", "quantita", "scadenza", "note"]:
        if campo in data:
            fields.append(f"{campo} = ?")
            values.append(data[campo])
    if fields:
        values.append(id)
        conn.execute(f"UPDATE prodotti SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()
    # Logga consumo se quantita è diminuita
    if p and "quantita" in data and data["quantita"] < p["quantita"]:
        log_movimento(
            nome=p["nome"], tipo="consumo",
            ean=p["ean"] or "", marca=p["marca"] or "",
            categoria=p["categoria"] or "",
            quantita=p["quantita"] - data["quantita"]
        )
    aggiorna_sensori_ha()
    return jsonify({"ok": True})

@app.route("/api/prodotti/<int:id>", methods=["DELETE"])
def elimina_prodotto(id):
    conn = get_db()
    p = conn.execute("SELECT * FROM prodotti WHERE id = ?", (id,)).fetchone()
    conn.execute("DELETE FROM prodotti WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    if p:
        log_movimento(
            nome=p["nome"], tipo="eliminato",
            ean=p["ean"] or "", marca=p["marca"] or "",
            categoria=p["categoria"] or "", quantita=p["quantita"]
        )
    aggiorna_sensori_ha()
    return jsonify({"ok": True})

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route("/api/test-telegram", methods=["GET"])
def test_telegram():
    opts = get_options()
    token = opts.get("telegram_token", "")
    chat_id_raw = opts.get("telegram_chat_id", "")
    if not token or not chat_id_raw:
        return jsonify({"ok": False, "errore": "Token o chat_id non configurati"})
    
    chat_ids = [c.strip() for c in str(chat_id_raw).split(",") if c.strip()]
    msg = "🧪 *Test Dispensa Manager*\n\nLe notifiche Telegram funzionano correttamente! ✅"
    
    risultati = []
    for cid in chat_ids:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
            risultati.append({"chat_id": cid, "ok": r.status_code == 200})
        except Exception as e:
            risultati.append({"chat_id": cid, "ok": False, "errore": str(e)})
    
    return jsonify({"risultati": risultati})

@app.route("/api/report", methods=["GET"])
def report_dispensa():
    conn = get_db()
    prodotti = conn.execute("SELECT * FROM prodotti ORDER BY scadenza ASC NULLS LAST").fetchall()
    conn.close()

    oggi = datetime.now().date()
    opts = get_options()
    giorni_soglia = opts.get("giorni_alert_scadenza", 3)
    token = opts.get("telegram_token", "")
    chat_id_raw = opts.get("telegram_chat_id", "")

    if not token or not chat_id_raw:
        return jsonify({"ok": False, "errore": "Telegram non configurato"})

    chat_ids = [c.strip() for c in str(chat_id_raw).split(",") if c.strip()]

    in_scadenza = []
    esauriti = []
    ok = []

    for p in prodotti:
        if p["quantita"] <= 0:
            esauriti.append(p)
            continue
        if p["scadenza"]:
            try:
                scad = datetime.strptime(p["scadenza"], "%Y-%m-%d").date()
                giorni = (scad - oggi).days
                if giorni <= giorni_soglia:
                    in_scadenza.append({"nome": p["nome"], "giorni": giorni, "quantita": p["quantita"]})
                else:
                    ok.append(p)
            except:
                ok.append(p)
        else:
            ok.append(p)

    msg = f"📦 *Report Dispensa*\n_{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n\n"
    msg += f"*Totale prodotti: {len(prodotti)}*\n\n"

    if in_scadenza:
        msg += "⚠️ *In scadenza:*\n"
        for p in in_scadenza:
            if p["giorni"] < 0:
                label = "scaduto!"
            elif p["giorni"] == 0:
                label = "scade oggi!"
            elif p["giorni"] == 1:
                label = "scade domani"
            else:
                label = f"tra {p['giorni']} giorni"
            msg += f"  • {p['nome']} ×{p['quantita']} — _{label}_\n"
        msg += "\n"

    if esauriti:
        msg += "❌ *Esauriti:*\n"
        for p in esauriti:
            msg += f"  • {p['nome']}\n"
        msg += "\n"

    if ok:
        msg += "✅ *In dispensa:*\n"
        for p in ok:
            msg += f"  • {p['nome']} ×{p['quantita']}\n"

    for cid in chat_ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print(f"Errore Telegram report {cid}: {e}")

    return jsonify({"ok": True, "totale": len(prodotti)})

@app.route("/api/barcode-cache/<ean>", methods=["DELETE"])
def elimina_barcode_cache(ean):
    conn = get_db()
    conn.execute("DELETE FROM barcode_cache WHERE ean = ?", (ean,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/statistiche", methods=["GET"])
def statistiche():
    conn = get_db()
    oggi = datetime.now().date()
    mese_fa = (oggi.replace(day=1)).strftime("%Y-%m-%d")

    # Totale movimenti per tipo
    acquisti = conn.execute("SELECT COUNT(*) as n FROM storico_movimenti WHERE tipo='acquisto'").fetchone()["n"]
    consumi = conn.execute("SELECT COUNT(*) as n FROM storico_movimenti WHERE tipo='consumo'").fetchone()["n"]
    eliminati = conn.execute("SELECT COUNT(*) as n FROM storico_movimenti WHERE tipo='eliminato'").fetchone()["n"]

    # Prodotti più acquistati (top 5)
    top_acquistati = conn.execute("""
        SELECT nome, marca, SUM(quantita) as totale
        FROM storico_movimenti WHERE tipo='acquisto'
        GROUP BY ean ORDER BY totale DESC LIMIT 5
    """).fetchall()

    # Prodotti più consumati (top 5)
    top_consumati = conn.execute("""
        SELECT nome, marca, SUM(quantita) as totale
        FROM storico_movimenti WHERE tipo='consumo'
        GROUP BY ean ORDER BY totale DESC LIMIT 5
    """).fetchall()

    # Acquisti questo mese
    acquisti_mese = conn.execute("""
        SELECT COUNT(*) as n FROM storico_movimenti
        WHERE tipo='acquisto' AND data >= ?
    """, (mese_fa,)).fetchone()["n"]

    # Prodotti attualmente in dispensa per posizione
    per_posizione = conn.execute("""
        SELECT posizione, COUNT(*) as n FROM prodotti
        WHERE quantita > 0 GROUP BY posizione
    """).fetchall()

    conn.close()

    return jsonify({
        "totali": {
            "acquisti": acquisti,
            "consumi": consumi,
            "eliminati": eliminati,
            "acquisti_mese": acquisti_mese
        },
        "top_acquistati": [dict(r) for r in top_acquistati],
        "top_consumati": [dict(r) for r in top_consumati],
        "per_posizione": [dict(r) for r in per_posizione]
    })

@app.route("/api/sync-ha", methods=["GET"])
def sync_ha():
    try:
        aggiorna_sensori_ha()
        return jsonify({"ok": True, "message": "Sensori aggiornati"})
    except Exception as e:
        return jsonify({"ok": False, "errore": str(e)}), 500

if __name__ == "__main__":
    init_db()
    print("Dispensa Manager avviato su porta 5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
