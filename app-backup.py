import psycopg2
from flask import Flask, request, jsonify
from flask_restful import Resource, Api
import jwt
from functools import wraps
import os
from dotenv import load_dotenv

app = Flask(__name__)
api = Api(app, prefix='/api')

load_dotenv()
REGION = os.getenv('REGION')
USER_POOL_ID = os.getenv('USER_POOL_ID')
APP_CLIENT_ID = os.getenv('APP_CLIENT_ID')
ISSUER = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
JWKS_URL = f'{ISSUER}/.well-known/jwks.json'

HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PWD = os.getenv('DB_PWD')

db_connection = {
    'host': HOST,
    'database': DB_NAME,
    'user': DB_USER,
    'password': DB_PWD
}


def get_tenantid(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)

        if not auth_header:
            return {'message': 'Authorization header is missing'}, 401

        token = auth_header.split(' ')[1]

        # get the public key from idp, Amazon Cognito
        jwks_client = jwt.PyJWKClient(JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        if not auth_header:
            return {'message': 'Authorization header is missing'}, 401

        try:
            decoded = jwt.decode(                
                token,
                signing_key.key,
                algorithms=['RS256'],
                audience=APP_CLIENT_ID,
                issuer=ISSUER
            )
            ##⬇️custom:tenant_id 값을 가져 오는 걸로 코드 수정 필요
            tenant_id = decoded.get('tenant_id')

            if not tenant_id:
                return {'message': 'Tenant ID not found in JWT token'}, 401

            return function(tenant_id, *args, **kwargs)
        except jwt.InvalidTokenError as e:
            return {'message': f'Invalid JWT token: {str(e)}'}, 401

    return decorated_function


def get_db_connection():
    conn = psycopg2.connect(**db_connection)
    return conn

class TenantRecords(Resource):
    def get(self, tenant_id):
        conn = get_db_connection()
        cursor = conn.cursor()

        query = '''
            SELECT * FROM records
            WHERE tenant_id = %s;
        '''

        cursor.execute(query, (tenant_id,))
        records = cursor.fetchall()

        output = []

        for record in records:
            record_data = {
                'record_id': record[0],
                'tenant_id': record[1],
                'user_name': record[2],
                'clock_in': record[3].isoformat(),
                'clock_out': record[4].isoformat() if record[4] else None
            }
            output.append(record_data)

        cursor.close()
        conn.close()

        return jsonify(output)

    def post(self, tenant_id):
        data = request.get_json()
        action = data.get('action')
        user_name = data.get('user_name')

        conn = get_db_connection()
        cursor = conn.cursor()

        if action == 'clock_in':
            query = '''
                INSERT INTO records (tenant_id, user_name, clock_in)
                VALUES (%s, %s, NOW())
                RETURNING record_id;
            '''
            cursor.execute(query, (tenant_id, user_name))
            record_id = cursor.fetchone()[0]
            conn.commit()

            cursor.close()
            conn.close()

            return {'message': 'Clock-in created', 'record_id': record_id}, 201

        elif action == 'clock_out':
            query = '''
                UPDATE records
                SET clock_out = NOW()
                WHERE tenant_id = %s AND user_name = %s AND clock_out IS NULL
                RETURNING record_id;
            '''
            cursor.execute(query, (tenant_id, user_name))
            result = cursor.fetchone()

            if result:
                record_id = result[0]
                conn.commit()
                cursor.close()
                conn.close()
                return {'message': 'Clock-out updated', 'record_id': record_id}, 200
            else:
                cursor.close()
                conn.close()
                return {'message': 'No clock-in found to update'}, 404

        else:
            cursor.close()
            conn.close()
            return {'message': 'Invalid action'}, 400


api.add_resource(TenantRecords, '/api/records/<string:tenant_id>')


if __name__ == '__main__':
    app.run(debug=True)
