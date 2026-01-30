# Flou Backend

API backend para Flou - Asistente de salud mental para estudiantes universitarios.

## 🚀 Tecnologías

- **FastAPI**: Framework web moderno y rápido
- **Supabase**: Base de datos PostgreSQL y autenticación
- **Python 3.10+**: Lenguaje de programación
- **Uvicorn**: Servidor ASGI

## 📋 Requisitos

- Python 3.10 o superior
- Cuenta de Supabase
- Variables de entorno configuradas

## 🔧 Instalación Local

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

## ⚙️ Variables de Entorno

Crea un archivo `.env` con:

```env
SUPABASE_URL=tu_supabase_url
SUPABASE_KEY=tu_supabase_service_role_key
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8081"]
```

## 🏃 Ejecutar Localmente

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

La API estará disponible en: http://localhost:8000

## 📚 Documentación

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

## 🐳 Docker

```bash
# Construir imagen
docker build -t flou-backend .

# Ejecutar contenedor
docker run -p 8000:8000 --env-file .env flou-backend
```

## 🌐 Despliegue en Render

1. Conecta tu repositorio de GitHub
2. Configura las variables de entorno en Render
3. Render detectará automáticamente el `Dockerfile`
4. El servicio se desplegará automáticamente

### Variables de Entorno en Render:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `ALLOWED_ORIGINS` (incluir la URL de tu app móvil)

## 📁 Estructura del Proyecto

```
flou_backend/
├── app/
│   ├── core/           # Configuración y utilidades
│   ├── routers/        # Endpoints de la API
│   ├── schemas/        # Modelos Pydantic
│   ├── services/       # Lógica de negocio
│   └── main.py         # Punto de entrada
├── Dockerfile          # Configuración Docker
├── requirements.txt    # Dependencias Python
└── .env.example        # Ejemplo de variables de entorno
```

## 🔒 Seguridad

- Autenticación con JWT de Supabase
- CORS configurado
- Variables de entorno para secretos
- Row Level Security en Supabase

## 📝 Endpoints Principales

### Profiles
- `GET /api/v1/profiles/me` - Obtener perfil del usuario
- `PATCH /api/v1/profiles/settings` - Actualizar configuración
- `GET /api/v1/profiles/stats` - Estadísticas del usuario
- `PUT /api/v1/profiles/update` - Actualizar información del perfil

### Wellness
- `POST /api/v1/wellness/check-in` - Guardar check-in diario
- `POST /api/v1/wellness/energy` - Obtener ejercicio por nivel de energía
- `GET /api/v1/wellness/motivation` - Mensaje motivacional

### Info
- `GET /api/v1/info/content` - Contenido educativo

## 🤝 Contribuir

Este proyecto sigue las mejores prácticas de Python:
- Type hints en todas las funciones
- Docstrings en español
- Principios SOLID
- Clean Code

## 📄 Licencia

Privado - Todos los derechos reservados
