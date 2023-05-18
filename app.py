import os
from dotenv import load_dotenv
import psycopg2
from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from functools import wraps
from auth import get_tenantid
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*', 'methods': ['POST', 'OPTIONS', 'GET'], 'headers': ['Content-Type', 'Authorization']}})
api = Api(app)

load_dotenv()
# REGION = os.getenv('REGION')
# USER_POOL_ID = os.getenv('USER_POOL_ID')
# APP_CLIENT_ID = os.getenv('APP_CLIENT_ID')
# ISSUER = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
# JWKS_URL = f'{ISSUER}/.well-known/jwks.json'

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

# def get_tenantid(function):
#     @wraps(function)
#     def decorated_function(*args, **kwargs):
#         auth_header = request.headers.get('Authorization', None)

#         if not auth_header:
#             return {'message': 'Authorization header is missing'}, 401

#         # token = auth_header.split(' ')[1]
#         token = auth_header

#         try:
#             # Fetch the JSON Web Key Set (JWKS) from Amazon Cognito
#             session = Session()
#             jwks = session.get(JWKS_URL).json()

#             # Decode and validate the ID token
#             decoded = jwt.decode(
#                 token,
#                 jwks,
#                 claims_options={
#                     'iss': {'essential': True, 'values': [ISSUER]},
#                     'aud': {'essential': True, 'values': [APP_CLIENT_ID]}
#                 }
#             )

#             # Extract the tenant_id from the decoded token
#             tenant_id = decoded.get('custom:tenant_id')
#             tenant_name = decoded.get('custom:tenant_name')
#             tenant_tier = decoded.get('custom:tenant_tier')
#             user_role = decoded.get('custom:user_role')

#             if not tenant_id:
#                 return {'message': 'Tenant ID not found in JWT token'}, 401

#             print(f"Tenant ID: {tenant_id}, Tenant Name: {tenant_name}, Tenant Tier: {tenant_tier}, User Role: {user_role}", )
#             kwargs['tenant_id'] = tenant_id
#             kwargs['tenant_name'] = tenant_name
#             kwargs['tenant_tier'] = tenant_tier
#             kwargs['user_role'] = user_role
#             return function(*args, **kwargs)

#         except JoseError as e:
#             return {'message': f'Invalid JWT token: {str(e)}'}, 401

#     return decorated_function


def get_db_connection():
    conn = psycopg2.connect(**db_connection)
    return conn


class TenantRecords(Resource):
    @get_tenantid
    def get(self, *, tenant_id, **kwargs):
        # data = request.get_json()
        # user_name = data.get('user_name')
        # user_name = request.args.get('user_name')
        user_role = kwargs.get('user_role')
        user_name = kwargs.get('user_name')
        print(f"tenant_id: {tenant_id}")
        print(f"user_role", kwargs.get('user_role'))
        print(f"user_name", kwargs.get('user_name'))

        query = '''
            SELECT * FROM records
            WHERE tenant_id = %s
        '''
        params = [tenant_id]

        if user_role != 'admin':
            query += ' AND user_name = %s'
            params.append(user_name)

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
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
        print(jsonify(output))

        return jsonify(output)

    @get_tenantid
    def post(self, *, tenant_id, **kwargs):
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


api.add_resource(TenantRecords, '/api/records')

if __name__ == '__main__':
    app.run(debug=True)





