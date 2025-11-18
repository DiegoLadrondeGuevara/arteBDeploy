import json
import boto3
import uuid
import os

s3_client = boto3.client('s3')
# Lee el nombre de la tabla de las variables de entorno
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'usuario_bd')
# Lee el nombre del bucket S3 de las variables de entorno
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'mi-bucket-imagenes-usuarios') 

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def lambda_handler(event, context):
    # Definición de encabezados CORS
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*' # Habilitado por el API Gateway, pero se incluye por seguridad
    }
    
    try:
        # Parse del body
        body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
        
        # Obtener token del header Authorization
        headers = event.get('headers', {})
        # Buscar en 'Authorization' o 'authorization' (API Gateway puede normalizar)
        auth_header = headers.get('Authorization', headers.get('authorization', ''))
        token = auth_header.replace('Bearer ', '')
        
        if not token:
            return {
                'statusCode': 401,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Token no proporcionado'})
            }
        
        # Buscar usuario por token (Scan - Nota: Usar GSI si fuera un sistema en producción real)
        response = table.scan(
            FilterExpression='#token = :token',
            ExpressionAttributeNames={'#token': 'token'},
            ExpressionAttributeValues={':token': token},
            Limit=1 # Solo necesitamos uno
        )
        
        if not response['Items']:
            return {
                'statusCode': 401,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Token inválido'})
            }
        
        user = response['Items'][0]
        user_id = user['user_id']
        
        # Obtener tipo de archivo y generar nombre único
        file_extension = body.get('fileExtension', 'jpg')
        content_type = body.get('contentType', 'image/jpeg')
        file_name = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"users/{user_id}/{file_name}"
        
        # Generar URL prefirmada para subir la imagen (PUT)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=300 # URL válida por 5 minutos
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'URL de subida generada',
                'uploadUrl': presigned_url,
                'imageKey': s3_key,
                'expiresIn': 300
            })
        }
        
    except Exception as e:
        print(f"Error en GetUploadUrl: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'details': str(e)
            })
        }