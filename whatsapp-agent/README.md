# Agente de WhatsApp (Meta Cloud API + Claude)

FastAPI + Claude con herramientas y memoria por número (SQLite).

## 1. Configurar Meta
1. https://developers.facebook.com → *Crear app* → tipo **Business** → añade el producto **WhatsApp**.
2. En *WhatsApp > API Setup* obtén el **Phone number ID** y un token temporal (para producción crea un
   **System User** con token permanente y permisos `whatsapp_business_messaging` y `whatsapp_business_management`).
3. *App settings > Basic* → copia el **App Secret** (`WA_APP_SECRET`).
4. En API Setup añade tu número como destinatario de prueba.

## 2. Ejecutar local
```bash
cd whatsapp-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # rellena los valores
uvicorn app.main:app --port 8000
ngrok http 8000        # URL pública HTTPS
```

## 3. Registrar el webhook
En *WhatsApp > Configuration > Webhook*:
- Callback URL: `https://<tu-ngrok>/webhook`
- Verify token: el mismo `WA_VERIFY_TOKEN`
- Suscríbete al campo **messages**.

Escribe al número de prueba desde tu WhatsApp y el agente responde.

## 4. Personalizar
- `app/config.py` → `SYSTEM_PROMPT` (rol y tono).
- `app/tools.py` → herramientas reales (ERP, CRM, agenda...).
- `app/store.py` → cambia SQLite por Postgres/Redis si escalas a varias instancias.

## 5. Producción
- Despliega en Railway/Render/Fly.io/Cloud Run con HTTPS y un volumen persistente (o Postgres).
- Ventana de 24 h: fuera de ella solo puedes enviar **plantillas** aprobadas.
- Para salir del modo prueba: verificación del negocio en Meta y número propio.
- Nunca subas `.env`; ya está en `.gitignore`.
