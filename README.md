# kimi-monitor

Monitor en tiempo real de las cuotas del **Kimi Coding Plan** de Moonshot AI:
**5 Hours Quota**, **Weekly Quota** y **Monthly Total Quota** (más el límite de
requests en paralelo).

Incluye una **TUI** (interfaz en terminal) con barras de progreso, countdown al
reset y sparkline de historial, más un **daemon de alertas por Telegram** que te
avisa cuando pasas ciertos umbrales de consumo.

![status](https://img.shields.io/badge/status-funcionando-brightgreen) ![python](https://img.shields.io/badge/python-3.10%2B-blue)

---

## Tabla de contenidos

1. [Requisitos](#requisitos)
2. [Instalación](#instalación)
3. [Conseguir tu API key](#conseguir-tu-api-key)
4. [Uso](#uso)
5. [Alertas por Telegram](#alertas-por-telegram)
6. [Daemon en background (macOS)](#daemon-en-background-macos)
7. [Daemon en background (Linux / Ubuntu 22.04+)](#daemon-en-background-linux--ubuntu-2204)
8. [Configuración](#configuración)
9. [Solución de problemas](#solución-de-problemas)
10. [Cómo funciona (notas técnicas)](#cómo-funciona-notas-técnicas)
11. [Estructura del proyecto](#estructura-del-proyecto)

---

## Requisitos

- **Python 3.10+** (`python3 --version`)
- Una **suscripción activa** al Kimi Coding Plan (membresía Kimi con Kimi Code)
- macOS, Linux o WSL. La TUI necesita una terminal con color.
- (Opcional) Una cuenta de Telegram para las alertas

## Instalación

### Opción rápida (una línea)

```bash
curl -fsSL https://raw.githubusercontent.com/jpalmae/kimi-monitor/main/install.sh | bash
```

Esto clona el repo en `~/kimi-monitor`, crea el venv, instala todo y prepara el
`.env`. Para instalar en otra carpeta, añade la ruta al final:

```bash
curl -fsSL https://raw.githubusercontent.com/jpalmae/kimi-monitor/main/install.sh | bash -s -- ~/dev/kimi
```

Luego solo edita `.env` con tu API key (siguiente sección) y corre `python3 tui.py`.

### Opción manual

```bash
# 1. Clona y entra
git clone https://github.com/jpalmae/kimi-monitor.git
cd kimi-monitor

# 2. Crea y activa un entorno virtual
python3 -m venv .venv
source .venv/bin/activate      # en Windows: .venv\Scripts\activate

# 3. Instala dependencias (TUI + alertas + lint)
pip install -e ".[tui,telegram,dev]" httpx python-dotenv

# 4. Copia el archivo de entorno y añade tu API key (siguiente sección)
cp .env.example .env
```

## Conseguir tu API key

> ⚠️ **Importante**: necesitas la key del **Kimi Code (Coding Plan)**, formato
> `sk-kimi-xxx`. **NO** sirve una key de la plataforma abierta
> (`platform.kimi.com` / `api.moonshot.cn`, formato `sk-xxx`) — son sistemas
> distintos y no intercambiables.

Es la **misma** key que usas en Claude Code / Cline / opencode para conectarte
a Kimi. Formas de obtenerla:

**Opción A — Desde la consola de Kimi Code (recomendada)**
1. Entra a la consola de Kimi Code (ver https://www.kimi.com/code/docs/)
2. Crea una API key (formato `sk-kimi-xxxxxxxx...`) y cópiala

**Opción B — Desde opencode (si lo usas)**
```bash
cat ~/.local/share/opencode/auth.json
# busca "kimi-coding" o "kimi" -> copia el valor de "key"
```

**Opción C — Desde Claude Code**
Revisa `~/.claude/settings.json` o tus variables de entorno (`KIMI_API_KEY`,
`ANTHROPIC_API_KEY` con el base URL `https://api.kimi.com/coding`).

Una vez tengas la key, pégala en `.env`:
```bash
KIMI_API_KEY=sk-kimi-tu-api-key-aqui
```

Verifica que funciona:
```bash
python fetcher.py
# debe imprimir tu nivel de membresía y los % de cada cuota
```

---

## Uso

> Recuerda activar el entorno virtual primero: `source .venv/bin/activate`

### 1. TUI en vivo (uso principal)

```bash
python3 tui.py
```

Verás algo así:
```
╭──────────────────────────────────────────────────────────────────────────╮
│ kimi monitor — Kimi Coding Plan                                          │
╰──────────────────────────────────────────────────────────────────────────╯
  Personal   INTERMEDIATE   parallel 5
  5 Hours Quota
    ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░  6%   [18/300 Requests]
    resets in 4h 12m 7s
    at Mon Jul 20 19:45
  Weekly Quota
    ████░░░░░░░░░░░░░░░░░░░░░░░░░░  14%   […/… Tokens]
    resets in 2d 18h 55m
    at Wed Jul 22 11:59
  Monthly Total Quota
    █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  3%   […/… Tokens]
```

**Teclas:**
| Tecla | Acción |
|-------|--------|
| `r` | Refrescar ahora |
| `t` | Alternar tema claro/oscuro (persiste entre sesiones) |
| `m` | Mostrar/ocultar el panel Monthly |
| `q` | Salir |
| `^p` | Paleta de comandos |

**Colores de las barras** (según % consumido):
- 🟢 verde: < 50%
- 🟡 amarillo: 50–75%
- 🟠 naranja: 75–90%
- 🔴 rojo: ≥ 90%

Se auto-actualiza cada 60s (configurable) y guarda historial en `store.db` para
dibujar un sparkline debajo de cada barra cuando haya suficientes muestras
(aparece tras un par de minutos de uso).

El tema elegido con `t` (o con la paleta `^p`) se **persiste** en `store.db`,
así que se mantiene al cerrar y reabrir la app.

### 2. Lectura puntual (CLI, sin TUI)

```bash
python fetcher.py
```
Útil para scripts, cron, o revisar rápido desde SSH.

### 3. Daemon de alertas (foreground)

```bash
python3 alerts.py
```
Hace polling cada 5 min y envía alertas a Telegram si configuras las credenciales
(ver sección [Alertas por Telegram](#alertas-por-telegram)). Sin Telegram
configurado, solo loguea a consola.

---

## Alertas por Telegram

El daemon te avisa cuando una cuota cruza ciertos umbrales de consumo. Para
activarlo necesitas un bot de Telegram.

### Paso 1 — Crear el bot (una sola vez)

1. Abre [@BotFather](https://t.me/BotFather) en Telegram
2. Envía `/newbot` → elige un nombre y un username (debe terminar en `bot`)
3. BotFather te da un **token** con este formato: `123456789:ABCdefGhi...`
4. Cópialo

### Paso 2 — Configurar el chat (asistido)

El proyecto incluye un helper que **auto-detecta tu chat id** (no tienes que
buscarlo a mano):

```bash
python3 setup_telegram.py TU:TOKEN_AQUI
```
El script:
1. Valida el token
2. Te pide que abras Telegram y mandes `/start` a tu bot
3. Detecta tu chat id automáticamente
3. Envía un mensaje de prueba
4. Escribe todo en `config.toml`

### Paso 3 — (Alternativa) configuración manual

Si prefieres hacerlo a mano, edita `config.toml`:

```toml
[alerts]
tg_bot_token  = "123456789:ABCdefGhi..."
tg_chat_ids   = ["9876543210"]       # uno o varios destinatarios
thresholds        = [50, 75, 90, 100] # % en los que alerta (al subir)
recovered_below   = 20                # avisa "reset/available" al bajar de esto
min_interval_sec  = 60                # anti-spam: mín. segundos entre alertas
```

Para saber tu chat id manualmente: mándale cualquier mensaje a tu bot y abre
`https://api.telegram.org/bot<TOKEN>/getUpdates` en el navegador → busca
`chat.id`.

### Enviar a varios usuarios

Puedes enviar las alertas a **varios destinatarios** a la vez (tu móvil, un
compañero de equipo, un canal, etc.). En `config.toml`:

```toml
[alerts]
tg_chat_ids = ["9876543210", "1122334455", "-1009999999999"]   # varios
```

- Cada destinatario es un `chat_id` (numérico para usuarios; los **canales**
  empiezan con `-100`, p. ej. `-1009999999999`).
- **Cada usuario debe haber iniciado el bot** enviándole `/start` al menos una
  vez — Telegram bloquea a los bots enviar a quien no ha hablado con ellos.
  Para canales, añade el bot como administrador.
- También puedes usar el formato heredado con coma:
  `tg_chat_id = "9876543210,1122334455"`.
- Los ids se deduplican automáticamente.

### Cómo funciona el debounce (anti-spam)

Cada umbral dispara **una sola vez por ciclo de reset**. Ejemplo con
`thresholds = [50, 75, 90, 100]`:

- Al llegar al **50%** → avisa una vez
- Al llegar al **75%** → avisa una vez
- Si baja y vuelve a subir al 50% en el mismo ciclo → **NO** repite
- Cuando la cuota **resetea** (el `resetTime` cambia) → avisa "recovered" y
  se re-arma todo para el nuevo ciclo

El estado se persiste en `store.db`, así que sobrevive reinicios.

---

## Daemon en background (macOS)

Para que las alertas corran siempre (aunque cierres la terminal), usa launchd:

```bash
# 1. Edita launchd/com.kimi-monitor.alerts.plist y ajusta las rutas a tu home
#    (las líneas <string>/Users/TU_USUARIO/...</string>)

# 2. Instálalo
cp launchd/com.kimi-monitor.alerts.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kimi-monitor.alerts.plist
```

**Logs:** `~/Library/Logs/kimi-monitor-alerts.log`

**Gestión:**
```bash
# ver estado
launchctl list | grep kimi-monitor

# ver logs en vivo
tail -f ~/Library/Logs/kimi-monitor-alerts.log

# parar
launchctl unload ~/Library/LaunchAgents/com.kimi-monitor.alerts.plist

# reiniciar (tras cambiar config.toml)
launchctl unload ~/Library/LaunchAgents/com.kimi-monitor.alerts.plist
launchctl load   ~/Library/LaunchAgents/com.kimi-monitor.alerts.plist
```

---

## Daemon en background (Linux / Ubuntu 22.04+)

Usa **systemd** con un servicio de usuario (sin necesidad de root). El daemon
loguea al journal del sistema (no necesita archivo de log).

```bash
# 1. Edita systemd/kimi-monitor-alerts.service y reemplaza USERNAME por tu
#    usuario (y la ruta del proyecto si no está en ~/kimi-monitor).

# 2. Instálalo como servicio de usuario
mkdir -p ~/.config/systemd/user
cp systemd/kimi-monitor-alerts.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kimi-monitor-alerts

# 3. Para que el daemon siga corriendo aunque cierres sesión (importante en servidores)
loginctl enable-linger $USER
```

**Logs:** `journalctl --user -u kimi-monitor-alerts`

**Gestión:**
```bash
# ver estado
systemctl --user status kimi-monitor-alerts

# ver logs en vivo
journalctl --user -u kimi-monitor-alerts -f

# parar / iniciar / reiniciar (tras cambiar config.toml)
systemctl --user restart kimi-monitor-alerts
systemctl --user stop    kimi-monitor-alerts
systemctl --user start   kimi-monitor-alerts

# desinstalar
systemctl --user disable --now kimi-monitor-alerts
rm ~/.config/systemd/user/kimi-monitor-alerts.service
systemctl --user daemon-reload
```

> El servicio usa el Python del venv (`.venv/bin/python`) y lee `.env` +
> `config.toml` del directorio del proyecto (`WorkingDirectory`). Recuerda que
> `KIMI_API_KEY` debe estar en `.env` y los `tg_chat_ids` en `config.toml`.

> En Linux usa systemd o cron. Ejemplo de cron (cada 5 min):
> `*/5 * * * * cd /ruta/kimi-monitor && .venv/bin/python alerts.py >> /tmp/kimi.log 2>&1`

---

## Configuración

Todo lo configurable está en `config.toml`:

```toml
[monitor]
poll_interval = 300        # segundos entre polls del daemon de alertas

[tui]
refresh_interval = 60      # segundos entre refresh de la TUI
show_monthly = true        # mostrar el panel Monthly Total Quota

[kimi]
name = ""                  # (opcional) etiqueta amigable para la cuenta

[alerts]
tg_bot_token   = ""          # token de @BotFather (vacío = desactivado)
tg_chat_ids    = []          # uno o varios destinatarios (ver sección Telegram)
thresholds       = [50, 75, 90, 100]
recovered_below  = 20
min_interval_sec = 60
```

La API key va en `.env` (no en `config.toml`, para no commitearla por error):
```bash
KIMI_API_KEY=sk-kimi-tu-api-key-aqui
```

### Multi-cuenta (varias suscripciones)

Para monitorear **varias cuentas** del coding plan en una sola instancia (una
TUI con todas apiladas, un solo daemon que las pollée todas):

1. Copia el template y rellénalo:
   ```bash
   cp accounts.example.toml accounts.toml
   ```
2. Define una entrada `[[accounts]]` por cuenta:
   ```toml
   [[accounts]]
   name     = "Personal"
   api_key  = "sk-kimi-aaaa..."
   tg_chat_ids = ["111222333"]   # opcional: destinatarios solo para esta cuenta

   [[accounts]]
   name    = "Work"
   api_key = "sk-kimi-bbbb..."
   # sin tg_chat_ids -> usa los globales de config.toml
   ```
   `accounts.toml` está en `.gitignore` (no se sube a git), así que las API keys
   quedan solo en tu máquina.

- **Un solo daemon / una sola TUI** maneja todas las cuentas.
- El historial y el debounce de alertas son **por cuenta** (no se mezclan).
- Cada cuenta puede tener **destinatarios de Telegram propios** (`tg_chat_ids`
  en su bloque); si los omite, usa los globales de `config.toml`.
- Si una cuenta falla (key inválida, caducada), el daemon la marca
  `(fetch failed)` en la TUI y sigue con las demás sin detenerse.
- **Sin `accounts.toml`** el proyecto vuelve al modo single-cuenta usando
  `KIMI_API_KEY` de `.env` (compatible hacia atrás).

> El nivel de membresía y el límite de paralelismo de cada cuenta se leen
> automáticamente de la API; solo necesitas indicar `name` + `api_key`.

---

## Solución de problemas

**`KimiError: auth failed: use a Kimi Code (Coding Plan) key sk-kimi-xxx...` (401)**
Estás usando una key de la plataforma abierta (`sk-xxx` de platform.kimi.com /
api.moonshot.cn) o tu key caducó. Crea una key en la **consola de Kimi Code**
(formato `sk-kimi-xxx`) y actualiza `.env`.

**`KimiError: usage endpoint not found...` (404)**
El base URL debe ser `https://api.kimi.com/coding/v1`. No uses
`https://api.moonshot.cn/v1` ni la URL de la plataforma abierta.

**`KimiError: rate limited` (429)**
Estás polleando demasiado rápido. Sube `poll_interval` en `config.toml`.

**La TUI muestra `loading…` y no avanza**
Revisa que tienes red y que `python fetcher.py` funciona. Si hay un error de red,
el estado mostrará `[red]error: ...[/]`.

**`StoreError` / problemas con sqlite**
Borra la base local y vuelve a empezar: `rm store.db*`

**El daemon de launchd no arranca**
1. Verifica las rutas en el `.plist` (`python` y `alerts.py`)
2. Revisa el log: `cat ~/Library/Logs/kimi-monitor-alerts.log`
3. Prueba a mano primero: `cd kimi-monitor && .venv/bin/python alerts.py`

**Telegram no envía mensajes**
1. Confirma que mandaste `/start` al bot al menos una vez (Telegram bloquea bots
   hasta que el usuario inicia la conversación)
2. Verifica token y chat_id en `config.toml`
3. El daemon loguea el mensaje que enviaría si no hay Telegram configurado

---

## Cómo funciona (notas técnicas)

Kimi **no expone una API pública documentada** de cuotas, pero el endpoint
interno que usan el CLI y el dashboard **acepta la misma API key del coding
plan** como Bearer:

```
GET https://api.kimi.com/coding/v1/usages
Authorization: Bearer <sk-kimi-xxx>
User-Agent: KimiCLI/1.6
```

Respuesta relevante (los números pueden venir como strings):

```json
{
  "user": { "membership": { "level": "LEVEL_INTERMEDIATE" } },
  "subType": "TYPE_PURCHASE",
  "usage":  { "used": "…", "limit": "…", "resetTime": "2026-07-22T11:59:00Z" },
  "limits": [
    { "window": { "duration": 300, "timeUnit": "TIME_UNIT_MINUTE" },
      "detail": { "used": "18", "limit": "300", "resetTime": "2026-07-20T19:45:00Z" } }
  ],
  "totalQuota": { "limit": "…", "remaining": "…" },
  "parallel": { "limit": 5 }
}
```

Mapping `campo → cuota`:
| campo | cuota | reset |
|-------|-------|-------|
| `limits[]` con `window.duration=300` (min) | **5 Hours Quota** | `detail.resetTime` |
| `usage` | **Weekly Quota** (reset cada 7 días) | `usage.resetTime` |
| `totalQuota` | **Monthly Total Quota** | la API **no** expone su reset |
| `parallel.limit` | requests concurrentes máx. | — |

> ⚠️ **Advertencias**
> - El endpoint **no está documentado** y puede cambiar sin aviso (hay un
>   fallback automático a `/usage` singular si `/usages` da 404).
> - Es un `GET` de **solo lectura** y **no consume cuota**.
> - La 5h window es un **rate limit rodante** (requests), independiente de la
>   cuota semanal: aunque te quede semana, un pico fuerte en 5h te estrangula.
> - La cuota semanal no se acumula: lo no usado se pierde al reset.

---

## Estructura del proyecto

```
kimi-monitor/
├── tui.py              # TUI con textual (barras + countdown + sparkline)
├── fetcher.py          # llama al endpoint y parsea la respuesta
├── alerts.py           # daemon de alertas con debounce por ciclo
├── store.py            # sqlite: historial + estado de alertas
├── config.py           # lee config.toml / accounts.toml / .env
├── config.toml         # umbrales, intervalos, telegram (global)
├── accounts.example.toml  # template multi-cuenta (copia a accounts.toml)
├── setup_telegram.py   # helper para configurar Telegram (auto-detecta chat_id)
├── probe.py            # script de discovery (referencia, no se necesita)
├── .env / .env.example # API key (no commitear .env)
├── launchd/
│   └── com.kimi-monitor.alerts.plist   # daemon para macOS
├── systemd/
│   └── kimi-monitor-alerts.service     # daemon para Linux (systemd, usuario)
└── store.db            # sqlite autogenerado (historial + debounce)
```

## Licencia

MIT — ver [LICENSE](LICENSE). Kimi y Moonshot AI son marcas de Moonshot AI.
Este proyecto no está afiliado a Moonshot AI y solo lee datos que el
CLI/dashboard ya exponen.
Fork/adaptación de [zai-monitor](https://github.com/jpalmae/zai-monitor).
