# 🛒 Dispensa Manager — Home Assistant Add-on

[![Version](https://img.shields.io/badge/version-1.1.0-green)](https://github.com/elbarto8383/Dispensa-Manager/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HA](https://img.shields.io/badge/Home%20Assistant-Add--on-blue)](https://www.home-assistant.io/)

Un add-on per **Home Assistant OS** che trasforma il tuo smartphone in uno scanner di barcode per gestire la dispensa di casa. Integra notifiche Telegram, lista della spesa automatica, valori nutrizionali, statistiche sui consumi e integrazione con Alexa.

---

## ✨ Funzionalità

- 🌐 **Accesso remoto via ingress HA** — funziona anche da cellulare fuori rete, tramite il pannello laterale di Home Assistant
- 📱 **PWA iPhone/Android** — installabile come app, funziona offline
- 📦 **Scanner barcode** — scansiona i prodotti con la fotocamera (ZXing)
- 🗄️ **Posizione automatica** — Frigo 🧊 / Dispensa 🗄️ / Freezer ❄️ suggeriti dalla categoria
- 📅 **Scadenza suggerita** — calcolata automaticamente dalla categoria del prodotto
- 🔍 **OCR scadenza** — scansiona la data di scadenza con la fotocamera (Tesseract.js), supporta DD/MM/YYYY, MM/YYYY e mesi in italiano
- 📊 **Valori nutrizionali** — da Open Food Facts (energia, grassi, carboidrati, ecc.)
- 🏷️ **Nutri-Score** — visualizzato nel dettaglio prodotto
- 🗃️ **Cache locale** — i prodotti non trovati online vengono salvati per le scansioni future
- 🔍 **Multi-database** — Open Food Facts + Open Products Facts + Open Beauty Facts
- 🏠 **Sensori Home Assistant** — 3 sensori aggiornati in tempo reale
- 📲 **Notifiche Telegram** — su scadenza, esaurimento scorte, aggiornamenti
- 🛒 **Lista della spesa** — automatica quando un prodotto si esaurisce, con invio Telegram
- 📈 **Statistiche consumi** — prodotti più acquistati, consumati, per posizione
- 🔔 **Alexa** — annunci vocali tramite Alexa Media Player
- ⏰ **Automazioni HA** — report mattutino, sync all'avvio
- 🔗 **API REST completa** — per integrazioni personalizzate

---

## 🌐 Accesso remoto (novità v1.1.0)

A partire dalla versione 1.1.0 l'add-on usa l'**ingress di Home Assistant**: apparirà un'icona "Dispensa" nel menu laterale di HA, e funzionerà ovunque sia raggiungibile la tua istanza HA — anche da cellulare con dati mobili, fuori dalla rete di casa — senza bisogno di aprire porte sul router.

Con l'ingress attivo, il backend ascolta su una porta interna al container (5000), che **non viene mai esposta** sul tuo host: nessun rischio di conflitto con altri servizi, incluso un NAS Synology che usa già le porte 5000/5001 per il proprio DSM.

### Accesso LAN diretto (opzionale) e conflitti di porta

Se preferisci anche un accesso diretto via IP (ad es. per un tablet fisso in cucina), puoi attivarlo decommentando il blocco `ports` in `dispensa_manager/config.yaml`:

```yaml
ports:
  5000/tcp: null
ports_description:
  5000/tcp: "API REST Dispensa (accesso LAN diretto, opzionale)"
```

Usando `null` invece di un numero fisso, non devi scegliere la porta host nel file: dopo aver riavviato l'add-on, vai su **Impostazioni → Add-on, backup e Supervisor → Dispensa Manager → tab Rete**, e lì potrai scegliere/cambiare liberamente la porta host (ad es. `5050`) in qualsiasi momento, anche se gira su un Synology o un altro sistema dove 5000/5001 sono già occupate.

Se attivi l'accesso LAN diretto su una porta diversa da 5000, ricordati di impostare l'URL manuale nella schermata **Impostazioni** della PWA (es. `http://<ip-ha>:5050`), altrimenti l'app cercherà di default sulla porta 5000.

---

## 📋 Requisiti

- Home Assistant OS o Supervised
- Add-on **File Editor** o **Studio Code Server** (per copiare i file)
- Bot Telegram (opzionale, per le notifiche)
- Alexa Media Player (opzionale, per gli annunci vocali)

---

## 🚀 Installazione

### 1. Aggiungi il repository custom

Vai in HA → **Impostazioni** → **Add-on** → **Add-on Store** → ⋮ → **Repository** → incolla:

```
https://github.com/elbarto8383/Dispensa-Manager
```

Clicca **Aggiungi** → **Chiudi**.

### 2. Installa l'add-on

Cerca **Dispensa Manager** nell'Add-on Store → **Installa**.

### 3. Copia la PWA

Copia la cartella `www/dispensa/` in `/config/www/dispensa/` sul tuo Home Assistant.

### 4. Configura l'add-on

Vai nella scheda **Configurazione** dell'add-on e compila:

```yaml
telegram_token: "IL_TUO_BOT_TOKEN"       # opzionale
telegram_chat_id: "IL_TUO_CHAT_ID"       # opzionale, supporta più ID separati da virgola
giorni_alert_scadenza: 3                  # giorni prima della scadenza per l'alert
soglia_scorte_minime: 1                   # quantità minima prima di aggiungere alla lista spesa
```

> **Nota:** `telegram_chat_id` supporta più ID separati da virgola es. `123456,789012`

### 5. Avvia l'add-on

Clicca **Avvia** e verifica i log.

### 6. Accedi alla PWA

Apri nel browser:
```
http://IP_HOME_ASSISTANT:8123/local/dispensa/index.html
```

Su iPhone puoi installarla come app: **Condividi** → **Aggiungi a schermata Home**.

---

## 📱 PWA — Schermate

La PWA è composta da 5 sezioni accessibili dalla barra in basso:

| Schermata | Descrizione |
|-----------|-------------|
| 🏠 **Dispensa** | Lista prodotti con metriche (totale, in scadenza, esauriti) |
| 📷 **Scansiona** | Scanner barcode con ricerca automatica su Open Food Facts |
| 🛒 **Spesa** | Lista della spesa con spunta e invio Telegram |
| 📊 **Statistiche** | Consumi, acquisti, top prodotti, prodotti per posizione |
| ⚙️ **Impostazioni** | URL backend e configurazione alert scadenza |

---

## 🏠 Integrazione Home Assistant

### Sensori creati automaticamente

| Entità | Descrizione |
|--------|-------------|
| `sensor.dispensa_totale_prodotti` | Numero totale di prodotti |
| `sensor.dispensa_in_scadenza` | Prodotti in scadenza entro N giorni |
| `sensor.dispensa_esauriti` | Prodotti con quantità zero |

### configuration.yaml

```yaml
rest_command:
  report_dispensa:
    url: http://localhost:5000/api/report
    method: GET
  sync_dispensa:
    url: http://localhost:5000/api/sync-ha
    method: GET
  lista_spesa_telegram:
    url: http://localhost:5000/api/lista-spesa/invia-telegram
    method: GET
```

### Card dashboard

```yaml
type: entities
title: 🛒 Dispensa
entities:
  - entity: sensor.dispensa_totale_prodotti
    name: Prodotti totali
    icon: mdi:package-variant
  - entity: sensor.dispensa_in_scadenza
    name: In scadenza
    icon: mdi:calendar-alert
  - entity: sensor.dispensa_esauriti
    name: Esauriti
    icon: mdi:package-variant-remove
  - entity: script.report_dispensa
  - type: button
    name: 🛒 Invia Lista Spesa
    icon: mdi:cart
    tap_action:
      action: perform-action
      perform_action: rest_command.lista_spesa_telegram
```

### Card iframe PWA nella dashboard

```yaml
type: iframe
url: http://IP_HOME_ASSISTANT:8123/local/dispensa/index.html
aspect_ratio: 75%
title: 📦 Lista Prodotti Dispensa
```

---

## ⚙️ Automazioni consigliate

**Sync sensori all'avvio di HA:**
```yaml
alias: 🔄 Sync Dispensa all'avvio
description: Aggiorna i sensori della dispensa quando HA si avvia
trigger:
  - platform: homeassistant
    event: start
condition: []
action:
  - delay:
      seconds: 30
  - action: rest_command.sync_dispensa
mode: single
```

**Report mattutino su Telegram:**
```yaml
alias: 🌅 Report dispensa mattutino
description: Ogni mattina alle 8 invia il report dispensa su Telegram
trigger:
  - platform: time
    at: "08:00:00"
condition: []
action:
  - action: rest_command.report_dispensa
mode: single
```

**Alexa — avvisa prodotti in scadenza:**
```yaml
alias: 🔔 Alexa avvisa prodotti in scadenza
trigger:
  - platform: time
    at: "08:30:00"
condition:
  - condition: numeric_state
    entity_id: sensor.dispensa_in_scadenza
    above: 0
action:
  - action: notify.alexa_media_NOME_DISPOSITIVO
    data:
      message: >
        Attenzione! Hai {{ states('sensor.dispensa_in_scadenza') }} prodotti
        in scadenza in dispensa. Controlla l'app Dispensa per i dettagli.
      data:
        type: announce
mode: single
```

**Alexa — avvisa prodotti esauriti:**
```yaml
alias: 🔔 Alexa avvisa prodotti esauriti
trigger:
  - platform: numeric_state
    entity_id: sensor.dispensa_esauriti
    above: 0
condition: []
action:
  - action: notify.alexa_media_NOME_DISPOSITIVO
    data:
      message: >
        Attenzione! Hai {{ states('sensor.dispensa_esauriti') }} prodotti
        esauriti in dispensa. Ricordati di aggiungerli alla lista della spesa!
      data:
        type: announce
mode: single
```

---

## 🛒 Lista della Spesa

La lista della spesa è gestita automaticamente:

- Quando un prodotto scende a **quantità 0** viene aggiunto automaticamente alla lista
- Puoi aggiungere prodotti **manualmente** dalla schermata Spesa nella PWA
- **Spunta** gli articoli mentre sei al supermercato
- **Invia su Telegram** la lista prima di uscire
- **Rimuovi completati** per pulire la lista

---

## 📈 Statistiche

La schermata Statistiche mostra:

- **Acquisti totali** — numero di prodotti acquistati nel tempo
- **Consumi totali** — numero di prodotti consumati
- **Acquisti questo mese** — acquisti nel mese corrente
- **Prodotti per posizione** — quanti prodotti in Frigo, Dispensa, Freezer
- **Top 5 più acquistati** — prodotti acquistati più frequentemente
- **Top 5 più consumati** — prodotti consumati più frequentemente

> Le statistiche si accumulano automaticamente ad ogni aggiunta, consumo o eliminazione prodotto.

---

## 🌐 API Endpoints

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/prodotti` | Lista tutti i prodotti |
| POST | `/api/prodotti` | Aggiunge un prodotto |
| PUT | `/api/prodotti/<id>` | Aggiorna un prodotto |
| DELETE | `/api/prodotti/<id>` | Elimina un prodotto |
| GET | `/api/barcode/<ean>` | Cerca un prodotto per EAN |
| POST | `/api/barcode-cache` | Salva in cache locale |
| DELETE | `/api/barcode-cache/<ean>` | Rimuove dalla cache |
| GET | `/api/lista-spesa` | Lista della spesa |
| POST | `/api/lista-spesa` | Aggiunge alla lista spesa |
| PUT | `/api/lista-spesa/<id>` | Aggiorna elemento lista spesa |
| DELETE | `/api/lista-spesa/<id>` | Elimina elemento lista spesa |
| DELETE | `/api/lista-spesa/svuota-completati` | Rimuove completati |
| GET | `/api/lista-spesa/invia-telegram` | Invia lista su Telegram |
| GET | `/api/statistiche` | Statistiche consumi |
| GET | `/api/report` | Report completo su Telegram |
| GET | `/api/sync-ha` | Aggiorna sensori HA |
| GET | `/api/test-telegram` | Test notifiche Telegram |
| GET | `/api/health` | Stato del servizio |

---

## 🗄️ Database

L'add-on utilizza SQLite con le seguenti tabelle:

| Tabella | Descrizione |
|---------|-------------|
| `prodotti` | Inventario prodotti con EAN, nutriments, posizione, scadenza |
| `barcode_cache` | Cache locale per prodotti non trovati online |
| `lista_spesa` | Lista della spesa con stato completato |
| `storico_movimenti` | Log acquisti, consumi ed eliminazioni per le statistiche |

---

## 🔧 Struttura del progetto

```
Dispensa-Manager/
├── dispensa_manager/       # Add-on HAOS
│   ├── Dockerfile
│   ├── config.yaml
│   ├── app.py              # Backend Flask
│   └── requirements.txt
├── www/
│   └── dispensa/
│       └── index.html      # PWA frontend
├── repository.json         # Custom store HA
├── .gitignore
└── README.md
```

---

## 🔍 OCR Scadenza

Dalla schermata di conferma prodotto, accanto al campo data di scadenza è presente il pulsante 📷:

1. Clicca 📷 — si apre la fotocamera con una cornice verde
2. Inquadra la data di scadenza stampata sulla confezione
3. Clicca **📸 Scatta** — Tesseract.js analizza il testo
4. Se riconosce la data la compila automaticamente nel campo

**Formati riconosciuti:**
- `DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`
- `MM/YYYY` → imposta automaticamente l'ultimo giorno del mese (es. `07/2026` → `31/07/2026`)
- Mesi in italiano: `GEN 2026`, `GENNAIO 2026`, ecc.

> **Nota:** La prima volta Tesseract.js scarica il modello OCR (~5MB). Le volte successive è immediato. Funziona meglio su testi stampati chiari e con buona illuminazione.

---

## 📋 Changelog

### v1.0.2
- 🔍 OCR scadenza automatica con fotocamera (Tesseract.js)
- 📅 Supporto formato MM/YYYY → ultimo giorno del mese automatico
- 🗓️ Riconoscimento mesi in italiano (GEN, FEB, MAR, ecc.)

### v1.0.1
- 📊 Statistiche consumi (acquisti, consumi, top prodotti, per posizione)
- 🛒 Lista della spesa automatica con invio Telegram
- 🍽️ Valori nutrizionali e Nutri-Score da Open Food Facts
- 🗃️ Cache barcode locale per prodotti non trovati online
- 🔔 Integrazione Alexa Media Player per annunci vocali
- 📍 Posizione automatica (Frigo/Dispensa/Freezer) dalla categoria
- 📅 Scadenza suggerita automaticamente dalla categoria
- 🔍 Multi-database (Food + Products + Beauty Facts)
- 🏷️ Supporto più chat ID Telegram separati da virgola
- 🗑️ Endpoint pulizia cache barcode

### v1.0.0
- 🎉 Release iniziale
- Scanner barcode con ZXing
- Integrazione Open Food Facts
- Sensori Home Assistant
- Notifiche Telegram base

---

## 🤝 Contribuire

Pull request e issue sono benvenute! Se hai miglioramenti o nuove funzionalità da proporre, apri una issue o una PR.

---

## 📄 Licenza

MIT License — vedi [LICENSE](LICENSE) per i dettagli.

---

## 👤 Autore

Creato da **Bart** ([@elbarto8383](https://github.com/elbarto8383))

Sviluppato con ❤️ per la community di Home Assistant Italia.
