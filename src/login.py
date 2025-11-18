import json
import boto3
import hashlib
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
        password = body.get('password')
        
        # Validaciones
        if not email or not password:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Email y contraseña son requeridos'})
            }
        
        # Buscar usuario en DynamoDB
        response = table.get_item(Key={'email': email})
        
        if 'Item' not in response:
            return {
                'statusCode': 401,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Credenciales inválidas'})
            }
        
        user = response['Item']
        
        # Verificar contraseña
        hashed_password = hash_password(password)
        
        if user['password'] != hashed_password:
            return {
                'statusCode': 401,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Credenciales inválidas'})
            }
        
        # Generar nuevo token y actualizar en la base de datos
        new_token = generate_simple_token()
        
        table.update_item(
            Key={'email': email},
            UpdateExpression='SET #token = :token',
            ExpressionAttributeNames={'#token': 'token'},
            ExpressionAttributeValues={':token': new_token}
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'Login exitoso',
                'token': new_token,
                'user': {
                    'user_id': user.get('user_id'),
                    'email': user.get('email'),
                    'username': user.get('username')
                }
            })
        }
        
    except Exception as e:
        print(f"Error en Login: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'details': str(e)
            })
        }