# src/auth_checker.py
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

    auth_header = event.get("authorizationToken")
    method_arn = event.get("methodArn")

    if not auth_header or not auth_header.startswith("Bearer "):
        print("⛔ No viene Authorization en formato Bearer")
        return generate_policy("unauthorized", "Deny", method_arn)

    token = auth_header.replace("Bearer ", "").strip()

    # Buscar token en DynamoDB
    try:
        resp = table.scan(
            FilterExpression=Attr("token").eq(token),
            Limit=1
        )

        if resp.get("Items"):
            user = resp["Items"][0]
            print("🟢 Token válido para usuario:", user["email"])

            return generate_policy(user["user_id"], "Allow", method_arn)

        else:
            print("⛔ Token NO encontrado")
            return generate_policy("unauthorized", "Deny", method_arn)

    except Exception as e:
        print("🔥 ERROR AUTHORIZER:", str(e))
        return generate_policy("error", "Deny", method_arn)
