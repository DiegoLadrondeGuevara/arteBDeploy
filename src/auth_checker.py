import json
import boto3
import os
from boto3.dynamodb.conditions import Attr

DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def generate_policy(principal_id, effect, resource):
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        }
    }


def lambda_handler(event, context):

    print("🔎 EVENT AUTHORIZE:", json.dumps(event))

    method_arn = event.get("methodArn")

    # 1️⃣ Leer token normalizado desde TODOS los posibles lugares
    auth_header = None

    # A. El estándar para TOKEN authorizer
    if "authorizationToken" in event:
        auth_header = event["authorizationToken"]

    # B. Pero si API Gateway falló y lo mete en headers
    if not auth_header:
        headers = event.get("headers") or {}
        # normalizamos todas las keys a lowercase
        normalized = {k.lower(): v for k, v in headers.items()}
        auth_header = normalized.get("authorization")

    if not auth_header:
        print("⛔ No vino Authorization en ningún lugar")
        return generate_policy("unauthorized", "Deny", method_arn)

    # 2️⃣ Normalizar: ignorar mayúsculas/minúsculas y espacios
    auth_header = auth_header.strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    else:
        print("⛔ Authorization sin Bearer")
        return generate_policy("unauthorized", "Deny", method_arn)

    # 3️⃣ Buscar token en DynamoDB
    try:
        resp = table.scan(
            FilterExpression=Attr("token").eq(token),
            Limit=1
        )

        if resp.get("Items"):
            user = resp["Items"][0]
            print("🟢 Token válido para usuario:", user["email"])
            return generate_policy(user["user_id"], "Allow", method_arn)

        print("⛔ Token NO encontrado")
        return generate_policy("unauthorized", "Deny", method_arn)

    except Exception as e:
        print("🔥 ERROR AUTHORIZER:", str(e))
        return generate_policy("error", "Deny", method_arn)
