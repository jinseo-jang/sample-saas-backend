import os
from dotenv import load_dotenv
from functools import wraps
from flask import request
from authlib.jose import jwt
from authlib.jose.errors import JoseError
from requests import Session
import jwt as pyjwt

# Add your other constants like REGION, USER_POOL_ID, etc.
REGION = os.getenv('REGION')
USER_POOL_ID = os.getenv('USER_POOL_ID')
APP_CLIENT_ID = os.getenv('APP_CLIENT_ID')
ISSUER = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
JWKS_URL = f'{ISSUER}/.well-known/jwks.json'

print(JWKS_URL)

def get_tenantid(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        print("here", auth_header)

        if not auth_header:
            return {'message': 'Authorization header is missing'}, 401

        token = auth_header.split(' ')[1]
        # token = auth_header

        try:
            # Fetch the JSON Web Key Set (JWKS) from Amazon Cognito
            session = Session()
            jwks = session.get(JWKS_URL).json()
            print("JTWKS:", jwks)

            # Find the correct key in the JWKS
            jwk = None
            for key in jwks['keys']:
                print("KEY:", key['kid'])
                print("KID: ",pyjwt.get_unverified_header(token)['kid'])
                if key['kid'] == pyjwt.get_unverified_header(token)['kid']:
                    jwk = key
                    break

            if jwk is None:
                raise ValueError("No matching JSON Web Key found in the set")

            # # Decode and validate the ID token
            # decoded = pyjwt.decode(
            #     token,
            #     jwk,
            #     algorithms=['RS256'],
            #     options={'verify_signature': True, 'verify_exp': True},
            #     audience=APP_CLIENT_ID,
            #     issuer=ISSUER
            # )

            # # Decode and validate the ID token
            decoded = jwt.decode(
                token,
                jwks,
                claims_options={
                    'iss': {'essential': True, 'values': [ISSUER]},
                    'aud': {'essential': True, 'values': [APP_CLIENT_ID]}
                }
            )

            # Extract the tenant_id from the decoded token
            tenant_id = decoded.get('custom:tenant_id')
            tenant_name = decoded.get('custom:tenant_name')
            tenant_tier = decoded.get('custom:tenant_tier')
            user_role = decoded.get('custom:user_role')
            user_name = decoded.get('email')

            if not tenant_id:
                return {'message': 'Tenant ID not found in JWT token'}, 401

            print(f"Tenant ID: {tenant_id}, Tenant Name: {tenant_name}, Tenant Tier: {tenant_tier}, User Role: {user_role}", )
            kwargs['tenant_id'] = tenant_id
            kwargs['tenant_name'] = tenant_name
            kwargs['tenant_tier'] = tenant_tier
            kwargs['user_role'] = user_role
            kwargs['user_name'] = user_name
            return function(*args, **kwargs)

        except JoseError as e:
            return {'message': f'Invalid JWT token: {str(e)}'}, 401

    return decorated_function


