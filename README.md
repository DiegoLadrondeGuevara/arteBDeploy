# 🚀 API Gestión de Usuarios y Generación de Arte (Serverless)

Este proyecto implementa una API *serverless* utilizando el **Serverless Framework** sobre **AWS**. La aplicación gestiona el registro y autenticación de usuarios y ofrece un *pipeline* avanzado para **analizar imágenes subidas** por el usuario y generar **nuevas imágenes artísticas** utilizando Inteligencia Artificial (IA) externa (Replicate) y servicios de AWS (Rekognition).

## ⚙️ Arquitectura del Proyecto

La aplicación se compone de recursos principales gestionados a través de CloudFormation (vía Serverless Framework):

  * **AWS Lambda (Python 3.11):** Aloja las funciones de negocio.
  * **API Gateway:** Proporciona los *endpoints* HTTP REST para el frontend.
  * **Amazon DynamoDB:** Base de datos para la gestión de usuarios.
  * **Amazon S3:** Bucket para almacenar imágenes originales y las obras de arte generadas.
  * **Amazon Rekognition:** Utilizado para el análisis de etiquetas y emociones en la fase inicial de IA.
  * **AWS Secrets Manager:** Almacena de forma segura el token de la API de Replicate.
  * **Replicate:** Servicio externo para la generación de imágenes artísticas (Stable Diffusion).

## 🛠️ Requisitos

1.  **Node.js y NPM:** Para instalar el Serverless Framework.
2.  **Serverless Framework CLI:** Instalado globalmente (`npm install -g serverless`).
3.  **Python 3.11:** Con `pip` para gestionar dependencias.
4.  **Credenciales AWS:** Configurado con un usuario que tenga permisos para crear y modificar CloudFormation, IAM, Lambda, DynamoDB, S3, Secrets Manager y Rekognition.

## 📦 Estructura del Proyecto

```
api-gestion-usuarios/
├── serverless.yml            # Definición de la infraestructura (IAM, Lambdas, DynamoDB, S3, Secrets Manager)
├── requirements.txt          # Dependencias Python (replicate, requests, boto3)
└── src/
    ├── register.py           # Registro de usuario
    ├── login.py              # Autenticación de usuario
    ├── get_upload_url.py     # Generación de URL prefirmada de S3
    └── ai_generate.py        # Pipeline de Análisis (Rekognition) y Generación (Replicate)
```

## 🚀 Despliegue e Instalación

### 1\. Instalación de Plugins y Dependencias

Necesitamos el plugin que empaqueta las librerías de Python y las sube a Lambda.

```bash
# 1. Instalar el plugin de Python
sls plugin install -n serverless-python-requirements

# 2. Instalar las dependencias de Python localmente
pip install -r requirements.txt
```

### 2\. Configuración de la Clave Secreta

El token de la API de Replicate se almacena en el `serverless.yml` y se inyecta automáticamente en AWS Secrets Manager durante el despliegue.

  * Verifique que el campo `SecretString` en el recurso `ExternalApiKeySecret` del `serverless.yml` contenga su token de Replicate.

### 3\. Despliegue de la API

Despliegue todos los recursos a AWS. Usaremos el *stage* `dev` como ejemplo:

```bash
sls deploy --stage dev
```

Tras un despliegue exitoso, la salida de la consola le proporcionará los *endpoints* de API Gateway.

## 🔗 Endpoints Principales

Todos los *endpoints* son accedidos a través del URL base proporcionado por API Gateway.

| Función | Método | Path | Descripción |
| :--- | :--- | :--- | :--- |
| **Registro** | `POST` | `/auth/register` | Crea una nueva cuenta de usuario. |
| **Login** | `POST` | `/auth/login` | Autentica al usuario y devuelve un token (JWT, clave, etc.). |
| **Upload URL** | `POST` | `/images/upload-url` | Genera una URL prefirmada para que el usuario suba su imagen original directamente a S3. |
| **Generación IA**| `POST` | `/images/generate` | **El pipeline principal.** Analiza la imagen subida y devuelve una imagen artística generada por IA. |

### Flujo de la Generación de IA (`/images/generate`)

La función `ai_generate` sigue este proceso:

1.  **Input:** Recibe la clave S3 (`s3KeyToAnalyze`) de la imagen subida por el usuario.
2.  **Análisis (Rekognition):** Llama a Amazon Rekognition para detectar etiquetas (objetos, escenas) y emociones faciales.
3.  **Prompting:** Utiliza los datos de Rekognition para construir un *prompt* artístico y detallado.
4.  **Generación (Replicate):** Llama a la API de Replicate con el *prompt* generado (usando el token de Secrets Manager).
5.  **Almacenamiento (S3):** Descarga la imagen generada por la IA y la guarda en la carpeta `/users/{user_id}/processed/` de su bucket S3.
6.  **Output:** Devuelve la clave S3 de la nueva imagen generada.