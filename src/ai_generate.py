import json
import boto3
import os
import requests
import base64
import time # Usaremos esto para el nombre único del archivo

# --- Configuración Inicial ---
rekognition_client = boto3.client('rekognition')
secrets_client = boto3.client('secretsmanager')
s3_client = boto3.client('s3')

# Variables de entorno definidas en serverless.yml
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
EXTERNAL_SECRET_NAME = os.environ.get('EXTERNAL_SECRET_NAME')

# URL del endpoint de generación de imágenes de Leonardo.Ai
# NOTA: Debes verificar la documentación oficial para la URL exacta
LEONARDO_API_URL = "https://cloud.leonardo.ai/api/v1/generations" 

# --- Funciones de Utilidad ---

def get_api_key(secret_name):
    """Obtiene la clave API de forma segura desde Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"ERROR: No se pudo obtener la clave secreta: {e}")
        return None

def analyze_image_rekognition(bucket, key):
    """Analiza la imagen en S3 usando Rekognition para generar un prompt base."""
    try:
        # 1. Detección de Etiquetas (Objetos/Escenas)
        labels_resp = rekognition_client.detect_labels(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}},
            MaxLabels=10
        )
        labels = [l['Name'] for l in labels_resp['Labels']]

        # 2. Detección de Emociones (Si hay caras)
        emotions = []
        faces_resp = rekognition_client.detect_faces(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}},
            Attributes=['ALL']
        )
        if faces_resp['FaceDetails']:
            for face in faces_resp['FaceDetails']:
                emotions.extend([emo['Type'] for emo in face['Emotions'] if emo['Confidence'] > 90])

        # 3. Generación del Prompt Artístico (Lógica simple en Python)
        # Reemplaza esta lógica por un LLM si tienes uno disponible, pero para empezar,
        # una simple concatenación es suficiente.
        
        feeling = emotions[0].lower() if emotions else 'serenity and contemplation'
        scene = labels[0].lower() if labels else 'an abstract shape'
        
        prompt = (
            f"A vibrant, expressive digital painting in the style of Van Gogh, "
            f"featuring {scene}, capturing a dominant emotion of {feeling}. "
            f"Focus on dramatic lighting and thick, visible brushstrokes. Artistic, beautiful, 4k."
        )
        
        return prompt

    except Exception as e:
        print(f"Error en Rekognition: {e}")
        # Retorna un prompt por defecto si falla el análisis
        return "An inspiring digital art piece of a mountain landscape with deep artistic texture."


def generate_image_leonardo(prompt, api_key):
    """Llama a la API de Leonardo.Ai para generar la imagen."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 1. Crear la Generación (Solo la solicitud inicial)
    # Debes adaptar el modeloId y los datos a la API específica de Leonardo.Ai
    # Usaremos una estructura placeholder común para APIs de Stable Diffusion
    creation_data = {
        "prompt": prompt,
        "modelId": "6bef9f1b-29cb-40c7-b9c3-32e6503d297d", # Ejemplo de ID de modelo
        "width": 512,
        "height": 512,
        "num_images": 1,
        "public": False
    }
    
    try:
        # Paso 1: Inicializar la generación (POST)
        response = requests.post(
            f"{LEONARDO_API_URL}", 
            headers=headers, 
            json=creation_data
        )
        response.raise_for_status()
        
        generation_id = response.json()['sdGenerationJob']['generationId']
        
        # Paso 2: Esperar la Generación (Polling/GET)
        # La generación no es instantánea, por lo que la Lambda debe esperar
        time.sleep(10) # Espera inicial
        
        while True:
            status_response = requests.get(
                f"{LEONARDO_API_URL}/{generation_id}",
                headers=headers
            )
            status_response.raise_for_status()
            status_data = status_response.json()
            
            if status_data['generations_v2'][0]['status'] == 'COMPLETE':
                # La imagen viene en formato URL o base64 (depende de la API)
                # Si es URL, puedes descargarla. Aquí simularemos que es una URL
                return status_data['generations_v2'][0]['generated_images'][0]['url'] 
            
            if status_data['generations_v2'][0]['status'] == 'FAILED':
                raise Exception("Generación de imagen fallida en Leonardo.Ai")
            
            time.sleep(5) # Espera antes de volver a consultar
            
    except requests.exceptions.RequestException as e:
        print(f"Error en la API de Leonardo.Ai: {e}")
        return None
    except Exception as e:
        print(f"Error durante el proceso de generación: {e}")
        return None

def lambda_handler(event, context):
    cors_headers = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
    
    try:
        # --- Obtención de Datos de Entrada (Adaptar según cómo se envía el user_id y la clave S3) ---
        body = json.loads(event['body'])
        # La clave S3 de la imagen subida que el usuario quiere analizar
        s3_key_to_analyze = body.get('s3KeyToAnalyze') 
        # El ID de usuario (debería obtenerse decodificando el JWT del header de autorización)
        user_id = body.get('userId', 'anonymous') 

        if not s3_key_to_analyze:
            return {'statusCode': 400, 'headers': cors_headers, 'body': json.dumps({'error': 'Falta la clave S3 de la imagen a analizar.'})}

        # 1. Obtener la clave API
        api_key = get_api_key(EXTERNAL_SECRET_NAME)
        if not api_key:
            return {'statusCode': 500, 'headers': cors_headers, 'body': json.dumps({'error': 'Error de configuración: Clave API no disponible.'})}

        # 2. Análisis de Imagen
        prompt_artistico = analyze_image_rekognition(S3_BUCKET_NAME, s3_key_to_analyze)

        # 3. Generación de Imagen (Retorna una URL en este ejemplo)
        image_url = generate_image_leonardo(prompt_artistico, api_key)
        
        if not image_url:
            return {'statusCode': 500, 'headers': cors_headers, 'body': json.dumps({'error': 'Fallo la generación de la imagen de IA. Verificar logs.'})}

        # 4. (Opcional) Descargar y guardar el resultado en S3
        # Si la API devuelve una URL pública, puedes guardarla directamente o descargarla.
        # En este ejemplo, solo devolvemos la URL generada.
        
        # Si deseas guardarla en tu S3, descomenta este bloque:
        # processed_image_data = requests.get(image_url).content
        # processed_key = f"users/{user_id}/processed/arte-ia-{int(time.time())}.jpg"
        # s3_client.put_object(
        #     Bucket=S3_BUCKET_NAME,
        #     Key=processed_key,
        #     Body=processed_image_data,
        #     ContentType='image/jpeg'
        # )

        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'Imagen artística generada exitosamente.',
                'prompt_used': prompt_artistico,
                'generated_image_url': image_url # O 'new_image_key': processed_key si decides guardarla.
            })
        }

    except Exception as e:
        print(f"Error interno en lambda_handler: {str(e)}")
        return {'statusCode': 500, 'headers': cors_headers, 'body': json.dumps({'error': 'Error inesperado', 'details': str(e)})}