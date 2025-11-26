# src/auth_checker.py
import json
import boto3
import os

# Configuración
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def generate_policy(principal_id, effect, resource):
    """Genera el documento de política de IAM para el Authorizer."""
    # Este es el formato estandar que API Gateway espera
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }

def lambda_handler(event, context):
    
    auth_header = event.get('authorizationToken')
    method_arn = event.get('methodArn')

    # 1. Validación de Encabezado: Espera "Bearer <token>"
    if not auth_header or not auth_header.startswith('Bearer '):
        # Si el formato es incorrecto, deniega.
        return generate_policy('unauthorized', 'Deny', method_arn)

    token = auth_header.split(' ')[1]
    
    # 2. Búsqueda de Token en DynamoDB (Usando Scan, ineficiente pero simple)
    try:
        # Scanear toda la tabla buscando el token
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('token').eq(token)
        )
        
        if response['Count'] == 1:
            user = response['Items'][0]
            # 3. Éxito: Generar política de 'Allow'
            # Es vital usar un identificador único, como el user_id, como principalId
            return generate_policy(user['user_id'], 'Allow', method_arn)
        else:
            # 4. Fallo: Token no encontrado. Denegar
            return generate_policy('unauthorized', 'Deny', method_arn)

    except Exception as e:
        print(f"Error en Custom Authorizer (DynamoDB): {str(e)}")
        # 5. Error del servidor: Denegar por seguridad (esto se cachea)
        return generate_policy('internal_error', 'Deny', method_arn)