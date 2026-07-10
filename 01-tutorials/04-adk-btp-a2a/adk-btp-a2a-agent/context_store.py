# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextvars
import time
from threading import Lock
from google.auth.credentials import Credentials

# Thread-safe Request Isolation Container
request_credentials_ctx = contextvars.ContextVar("request_credentials", default=None)
request_client_ctx = contextvars.ContextVar("request_client_ctx", default=None)

DEFAULT_CACHE_VALIDITY=1800 #30 Minutes
# ----------------------------------------------------- #
# Token Cache Implementation
# ----------------------------------------------------- #
class TokenCredentialCache:

    # ----------------------------------------------------- #
    # Constructor
    # ----------------------------------------------------- #
    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_VALIDITY): 
        self._cache = {}
        self._ttl = ttl_seconds
        self._lock = Lock()  

    # ----------------------------------------------------- #
    # Get the credentials from cache if its not expired
    # If expired evict it so that we can get a new cred
    # ----------------------------------------------------- #
    def get(self, token_key: str) -> Credentials:
        with self._lock:
            if token_key in self._cache:
                expiry, creds = self._cache[token_key]
                if time.time() < expiry:
                    return creds
                else:
                    del self._cache[token_key]  # Evict expired cred
            return None

    # ----------------------------------------------------- #
    # Add cred to the cache
    # ----------------------------------------------------- #
    def set(self, token_key: str, creds: Credentials):
        with self._lock:
            expiry = time.time() + self._ttl
            self._cache[token_key] = (expiry, creds)

# ----------------------------------------------------- #
# Instantiate a global cache instance for the application
# ----------------------------------------------------- #
credential_cache = TokenCredentialCache(ttl_seconds=DEFAULT_CACHE_VALIDITY)