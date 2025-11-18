import json
import boto3
import hashlib
import uuid
from datetime import datetime
import secrets
import os

# Lee el nombre de la tabla de las variables de entorno
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'usuario_bd')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def hash_password(password):
    """Hashea la contraseña usando SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_simple_token():
    """Genera un token simple sin dependencias externas"""
    return secrets.token_urlsafe(32)

def lambda_handler(event, context):
    # Definición de encabezados CORS
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*' # Habilitado por el API Gateway, pero se incluye por seguridad
    }
    
    try:
        # Parse del body
        body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
        
        email = body.get('email')
        username = body.get('user') # Usando 'user' como en tu código original
        password = body.get('password')
        
        # Validaciones
        if not email or not username or not password:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Email, usuario y contraseña son requeridos'})
            }
        
        # Verificar si el email ya existe
        try:
            response = table.get_item(Key={'email': email})
            if 'Item' in response:
                return {
                    'statusCode': 409,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'El email ya está registrado'})
                }
        except Exception as e:
            print(f"Error al verificar email: {e}")
            # Se permite continuar o retornar un 500 si el error es grave
        
        # Crear nuevo usuario
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(password)
        token = generate_simple_token()
        
        # Guardar en DynamoDB
        table.put_item(
            Item={
                'email': email,
                'user_id': user_id,
                'username': username,
                'password': hashed_password,
                'token': token,
                's3_folder': f'users/{user_id}/', 
                'created_at': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 201,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'Usuario registrado exitosamente',
                'token': token,
                'user': {
                    'user_id': user_id,
                    'email': email,
                    'username': username
                }
            })
        }
        
    except Exception as e:
        print(f"Error en Registro: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'details': str(e)
            })
        }