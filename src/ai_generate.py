import json
import boto3
import os
import requests 
import base64
import time
import replicate # ¡Esta es la librería clave!

# --- Configuración Inicial ---
rekognition_client = boto3.client('rekognition')
secrets_client = boto3.client('secretsmanager')
s3_client = boto3.client('s3')

# Variables de entorno definidas en serverless.yml
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
EXTERNAL_SECRET_NAME = os.environ.get('EXTERNAL_SECRET_NAME')

# --- Funciones de Utilidad ---

def get_api_token(secret_name):
    """Obtiene el token de Replicate de forma segura desde Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        print(f"ERROR: No se pudo obtener el token de Replicate: {e}")
        return None

def analyze_image_rekognition(bucket, key):
    """Analiza la imagen en S3 usando Rekognition para generar un prompt base."""
    try:
        labels_resp = rekognition_client.detect_labels(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}}, MaxLabels=10
        )
        labels = [l['Name'] for l in labels_resp['Labels']]
        
        faces_resp = rekognition_client.detect_faces(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}}, Attributes=['ALL']
        )
        emotions = []
        if faces_resp['FaceDetails']:
            for face in faces_resp['FaceDetails']:
                emotions.extend([emo['Type'] for emo in face['Emotions'] if emo['Confidence'] > 90])

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
        return "An inspiring digital art piece of a mountain landscape with deep artistic texture, hyper-detailed."


def generate_image_replicate(prompt, api_token):
    """Genera la imagen usando un modelo de Stable Diffusion en Replicate."""
    
    # Se utiliza la librería oficial de Replicate
    client = replicate.Client(api_token=api_token)

    # Versión del modelo Stable Diffusion (ejemplo potente)
    model_version = "stability-ai/stable-diffusion:9a29a4c0299d5529f79612394593c66f616016a2d9806a654c6017367c3b1716" 
    
    try:
        output = client.run(
            model_version,
            input={
                "prompt": prompt,
                "width": 768,
                "height": 768,
                "num_outputs": 1,
            }
        )
        
        if output and isinstance(output, list) and output[0].startswith('http'):
            return output[0] # Retorna la URL de la imagen generada
        
        raise Exception("Replicate no devolvió una URL válida.")

    except Exception as e:
        print(f"Error en la API de Replicate: {e}")
        return None


def lambda_handler(event, context):
    cors_headers = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
    
    try:
        body = json.loads(event['body'])
        s3_key_to_analyze = body.get('s3KeyToAnalyze')
        user_id = body.get('userId', 'anonymous') 

        if not s3_key_to_analyze:
            return {'statusCode': 400, 'headers': cors_headers, 'body': json.dumps({'error': 'Falta la clave S3 de la imagen a analizar.'})}

        # 1. Obtener el token de Replicate
        api_token = get_api_token(EXTERNAL_SECRET_NAME)
        if not api_token:
            return {'statusCode': 500, 'headers': cors_headers, 'body': json.dumps({'error': 'Error de configuración: Token API no disponible.'})}

        # 2. Análisis de Imagen
        prompt_artistico = analyze_image_rekognition(S3_BUCKET_NAME, s3_key_to_analyze)
        print(f"Prompt generado por Rekognition: {prompt_artistico}")

        # 3. Generación de Imagen
        image_url = generate_image_replicate(prompt_artistico, api_token)
        
        if not image_url:
            return {'statusCode': 500, 'headers': cors_headers, 'body': json.dumps({'error': 'Fallo la generación de la imagen de IA. Verificar logs.'})}

        # 4. Descargar y guardar el resultado en S3
        processed_image_data = requests.get(image_url).content
        
        processed_key = f"users/{user_id}/processed/arte-ia-{int(time.time())}.jpg"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=processed_key,
            Body=processed_image_data,
            ContentType='image/jpeg'
        )

        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'Imagen artística generada y guardada.',
                'prompt_used': prompt_artistico,
                'new_image_key': processed_key
            })
        }

    except Exception as e:
        print(f"Error en lambda_handler: {str(e)}")
        return {'statusCode': 500, 'headers': cors_headers, 'body': json.dumps({'error': 'Error inesperado', 'details': str(e)})}