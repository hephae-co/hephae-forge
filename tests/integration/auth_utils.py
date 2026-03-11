"""Authentication utilities for robust emulator-based testing."""

import os
import httpx
import firebase_admin
from firebase_admin import auth

# Force emulator environment
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"

def init_test_firebase():
    """Initialize Firebase Admin for testing if not already initialized."""
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={'projectId': 'hephae-co-dev'})

async def get_emulator_token(email: str, password: str = "testpassword123") -> str:
    """Create a user in the emulator and return a real JWT ID Token.
    
    Uses the Firebase Auth REST API to sign in.
    """
    init_test_firebase()
    
    # 1. Ensure user exists in emulator
    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        user = auth.create_user(email=email, password=password)

    # 2. Use REST API to exchange credentials for an ID Token
    # The emulator REST API endpoint for signing in with password
    api_key = "fake-api-key" # Emulator doesn't validate API key
    url = f"http://localhost:9099/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        if resp.status_code != 200:
            raise Exception(f"Failed to get emulator token: {resp.text}")
        
        return resp.json()["idToken"]
