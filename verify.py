import os
from dotenv import load_dotenv
import jwt
from functools import wraps
from authlib.integrations.requests_client import AssertionSession
from authlib.jose import jwt
from authlib.jose.errors import JoseError
from requests import Session

load_dotenv()
TOKEN = os.getenv('MY_TOKEN')
REGION = os.getenv('REGION')
USER_POOL_ID = os.getenv('USER_POOL_ID')
APP_CLIENT_ID = os.getenv('APP_CLIENT_ID')
ISSUER = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
JWKS_URL = f'{ISSUER}/.well-known/jwks.json'

session = Session()
jwks = session.get(JWKS_URL).json()

# Decode and validate the ID token
decoded = jwt.decode(
    TOKEN,
    jwks,
    claims_options={
        'iss': {'essential': True, 'values': [ISSUER]},
        'aud': {'essential': True, 'values': [APP_CLIENT_ID]}
    }
)

print(decoded)
# jwks_client = jwt.PyJWKClient(JWKS_URL)
# print (JWKS_URL)
# signing_key = jwks_client.get_signing_key_from_jwt(token)

# print("here")

# token = jwt.decode(
#     token,
#     signing_key.key,
#     algorithms=["RS256"],
#     audience=APP_CLIENT_ID,
#     issuer=ISSUER
# )

# if token['token_use'] != 'id':
#     raise Exception('Invalid token_use')