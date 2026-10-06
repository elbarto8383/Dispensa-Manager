# Dispensa Manager — Guida installazione completa

## Struttura file

```
dispensa-addon/
├── config.yaml              ← configurazione add-on HAOS
├── Dockerfile               ← build container
├── ha_configuration.yaml    ← snippet da aggiungere a HA
└── dispensa_backend/
    └── app.py               ← backend Flask

dispensa-pwa/
└── index.html               ← PWA per iPhone
```

---

## Step 1 — Crea il Long-Lived Token su HA

1. Apri Home Assistant → clicca sul tuo profilo (in basso a sinistra)
2. Scorri fino a **"Token di accesso a lunga durata"**
3. Clicca **"Crea token"** → nome: `dispensa-api`
4. Copia il token — lo vedrai una volta sola!

---

## Step 2 — Installa l'add-on su HAOS

Su HAOS gli add-on custom si installano così:

1. Vai su **Impostazioni → Add-on → Store add-on**
2. Clicca i tre puntini in alto a destra → **"Repository"**
3. Alternativa più semplice: usa l'**SSH add-on** o **File Editor**
   e copia la cartella `dispensa-addon/` in `/addons/dispensa_manager/`

### Via SSH (metodo consigliato):
```bash
# Abilita SSH add-on in HA, poi:
scp -r ./dispensa-addon/ root@192.168.x.x:/addons/dispensa_manager/
scp -r ./dispensa-pwa/ root@192.168.x.x:/addons/dispensa_manager/pwa/
```

### Poi su HA:
1. **Impostazioni → Add-on** → clicca "Ricarica" (icona in alto)
2. Cerca "Dispensa Manager" → Installa
3. Vai su **Configurazione** dell'add-on e inserisci:
   - `telegram_token`: il token del tuo bot Telegram
   - `telegram_chat_id`: il tuo chat ID Telegram
   - `giorni_alert_scadenza`: 3 (o quello che preferisci)
4. **Avvia** l'add-on

---

## Step 3 — Configura Nginx (già presente sulla VM)

Aggiungi un server block per esporre la PWA e l'API:

```nginx
# /etc/nginx/sites-available/dispensa
server {
    listen 80;
    server_name dispensa.locale;  # o usa IP diretto

    # API backend
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE";
        add_header Access-Control-Allow-Headers "Content-Type";
    }

    # PWA
    location / {
        root /addons/dispensa_manager/pwa;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/dispensa /etc/nginx/sites-enabled/
nginx -t && nginx -s reload
```

---

## Step 4 — Configura Home Assistant

Apri `configuration.yaml` e aggiungi il contenuto di `ha_configuration.yaml`.

Poi riavvia HA:
```
Impostazioni → Sistema → Riavvia
```

Dopo il riavvio vedrai i sensori:
- `sensor.dispensa_totale_prodotti`
- `sensor.dispensa_in_scadenza`
- `sensor.dispensa_esauriti`

---

## Step 5 — Installa la PWA su iPhone

1. Apri Safari su iPhone
2. Vai su `http://192.168.x.x/` (il tuo IP con Nginx)
3. Tocca **Condividi** → **Aggiungi a schermata Home**
4. Si installa come app nativa!
5. Prima apertura: vai in **Impostazioni** (tab in basso) e inserisci l'URL del backend

---

## Endpoint API disponibili

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | /api/prodotti | Lista tutti i prodotti |
| POST | /api/prodotti | Aggiungi prodotto |
| PUT | /api/prodotti/{id} | Aggiorna prodotto |
| DELETE | /api/prodotti/{id} | Elimina prodotto |
| GET | /api/barcode/{ean} | Cerca EAN su Open Food Facts |
| GET | /api/health | Health check |

---

## Troubleshooting

**Il barcode non viene letto su Safari/iPhone:**
- Assicurati di usare HTTPS o localhost (Safari blocca la fotocamera su HTTP remoto)
- Soluzione: abilita HTTPS su Nginx con un certificato self-signed o usa Tailscale

**I sensori HA non si aggiornano:**
- Verifica che il Long-Lived Token sia corretto
- Controlla i log dell'add-on: Impostazioni → Add-on → Dispensa → Log

**Open Food Facts non trova il prodotto:**
- È normale per prodotti locali o molto specifici
- Inserisci manualmente nome e scadenza
