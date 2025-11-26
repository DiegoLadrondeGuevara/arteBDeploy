import json
import boto3
import uuid
import os

s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
dynamodb = boto3.resource('dynamodb')

DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'usuario_bd')
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'api-gestion-usuarios-dev-images-851725327526')

table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def lambda_handler(event, context):
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,GET,PUT,POST",
        "Content-Type": "application/json"
    }

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": cors_headers, "body": json.dumps({"ok": True})}

    try:
        body = json.loads(event.get("body", "{}") or "{}")

        # ---- Autenticación ----
        headers = event.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not auth_header:
            return {"statusCode": 401, "headers": cors_headers, "body": json.dumps({"error": "No token"})}

        token = auth_header.replace("Bearer ", "").strip()
        response = table.scan(
            FilterExpression="#t = :t",
            ExpressionAttributeNames={"#t": "token"},
            ExpressionAttributeValues={":t": token},
            Limit=1
        )
        if not response.get("Items"):
            return {"statusCode": 401, "headers": cors_headers, "body": json.dumps({"error": "Token invalido"})}

        user = response["Items"][0]
        user_id = user["user_id"]

        # ---- Parámetros ----
        file_name_original = body.get("fileName")
        if not file_name_original:
            return {"statusCode": 400, "headers": cors_headers, "body": json.dumps({"error": "Falta fileName"})}

        # ---- Generar key ----
        ext = file_name_original.split(".")[-1]
        file_uuid = f"{uuid.uuid4()}.{ext}"
        s3_key = f"users/{user_id}/{file_uuid}"

        # ---- URL prefirmada SIN ContentType ----
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ContentType": ""   # <- obligatorio vacío
            },
            ExpiresIn=300,
            HttpMethod="PUT"
        )


        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "uploadUrl": presigned_url,
                "s3Key": s3_key,
                "expiresIn": 300
            })
        }

    except Exception as e:
        print("ERROR generate upload url:", str(e))
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": str(e)})
        }
