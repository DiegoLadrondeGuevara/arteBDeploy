import json
import boto3
import uuid
import os

# Inicialización de clientes y variables de entorno
s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
dynamodb = boto3.resource('dynamodb')

# Variables de entorno
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'usuario_bd')
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'mi-bucket-imagenes-usuarios')

table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def lambda_handler(event, context):
    # Encabezados CORS
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    try:
        # --- 1. PROCESAR BODY ---
        body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})

        # --- 2. AUTENTICACIÓN ---
        headers = event.get('headers', {})
        auth_header = headers.get('Authorization', headers.get('authorization', ''))
        token = auth_header.replace('Bearer ', '').strip()

        if not token:
            print("ERROR: Token no proporcionado.")
            return {
                'statusCode': 401,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Token no proporcionado'})
            }

        response = table.scan(
            FilterExpression='#token = :token',
            ExpressionAttributeNames={'#token': 'token'},
            ExpressionAttributeValues={':token': token},
            Limit=1
        )

        if not response['Items']:
            print(f"ERROR: Token inválido o no encontrado: {token[:10]}...")
            return {
                'statusCode': 401,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Token inválido'})
            }

        user = response['Items'][0]
        user_id = user['user_id']
        print(f"Token validado para user_id: {user_id}")

        # --- 3. PARÁMETROS DEL FRONTEND ---
        file_name_original = body.get('fileName')
        content_type = body.get('fileType', 'image/jpeg')

        if not file_name_original:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Falta parámetro: fileName'})
            }

        # --- 4. GENERAR CLAVE S3 ---
        file_extension = file_name_original.split('.')[-1]
        file_name_uuid = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"users/{user_id}/{file_name_uuid}"

        # --- 5. GENERAR URL PREFIRMADA ---
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type,
                'ContentSha256': 'UNSIGNED-PAYLOAD'
            },
            ExpiresIn=300
        )

        # --- 6. RESPUESTA ---
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'URL de subida generada',
                'uploadUrl': presigned_url,
                's3Key': s3_key,
                'expiresIn': 300
            })
        }

    except Exception as e:
        print(f"Error fatal en GetUploadUrl: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'details': str(e)
            })
        }
