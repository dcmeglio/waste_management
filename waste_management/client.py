from datetime import datetime
import re
import time
import json
import jwt

import requests

from .const import API_KEY_AUTHENTICATION, API_KEY_CUSTOMER_SERVICES, API_KEY_USER_ACCOUNTS, REST_API_URL
from .Entities import AccountInfo, Service

class WMClient:
    def __init__(
        self, email, password
    ):
        self.email = email
        self.password = password
        self._session_token = None
        self._access_token = None
        self._refresh_token = None
        self._id_token = None
        self._user_id = None
        self._token_expires_time = None
        self._okta_access_token = None
        self._client_id = None
        self._issuer = None

    def _string_escape(self, input : str, encoding='utf-8'):
        return input.encode('latin1').decode('unicode-escape').encode('latin1').decode(encoding)

    def authenticate(self):
        self._apiKey = API_KEY_AUTHENTICATION
        data = self.api_post("user/authenticate", {"username": self.email, "password": self.password, "locale": "en_US"})
        response_data = data["data"]

        self._session_token = response_data["sessionToken"]
        self._access_token = response_data["access_token"]
        self._refresh_token = response_data["refresh_token"]
        self._id_token = response_data["id_token"]
        self._user_id = response_data["id"]
        self._token_expires_time = time.time() + response_data["expires_in"]
        decoded_jwt = jwt.decode(response_data["access_token"], options={"verify_signature": False})
        self._client_id = decoded_jwt["cid"]
        self._issuer = decoded_jwt["iss"]
        return data


    def okta_authorize(self):
        # get from access token issuer
        response = requests.get(self._issuer+"/v1/authorize", {"client_id": self._client_id, 
        "nonce": "x", "prompt": "none", 
        "response_mode": "okta_post_message", "response_type": "token", "state": "x", 
        "scope": "openid email offline_access", "redirect_uri": "https://www.wm.com", "sessionToken": self._session_token})
        response.raise_for_status()
        result = re.search("access_token\s*=\s*'(.+?)'", response.text, re.MULTILINE)
        self._okta_access_token = self._string_escape(result.group(1))   

    def get_accounts(self):
        self._apiKey = API_KEY_USER_ACCOUNTS
        
        response = requests.get(REST_API_URL + f"authorize/user/{self._user_id}/accounts", headers=self.headers, params={"timestamp": time.time()*1000, "lang":"en_US"})
        response.raise_for_status()
      
        jsonData = json.loads(response.content.decode("UTF-8"))

        results = []
        for acct in jsonData["data"]["linkedAccounts"]:
            results.append(AccountInfo(acct))
        return results

    def get_services(self, account_id):
        self._apiKey = API_KEY_CUSTOMER_SERVICES

        response = requests.get(REST_API_URL + f"account/{account_id}/services", headers = self.headers, params={"lang": "en_US","serviceChangeEligibility": "Y", "userId": self._user_id})
        response.raise_for_status()

        jsonData = json.loads(response.content.decode("UTF-8"))
        results = []
        for svc in jsonData["services"]:
            results.append(Service(svc))

        return results

    def get_service_pickup(self, account_id, service_id):
        self._apiKey = API_KEY_CUSTOMER_SERVICES

        response = requests.get(REST_API_URL + f"account/{account_id}/service/{service_id}/pickupinfo", headers=self.headers, params={"lang": "en_US", "checkAlerts":"Y", "userId": self._user_id})
        response.raise_for_status()

        jsonData = json.loads(response.content.decode("UTF-8"))

        pickupDates = []
        for dateStr in jsonData["pickupScheduleInfo"]["pickupDates"]:
            date = datetime.strptime(dateStr, "%m-%d-%Y")
            pickupDates.append(date)

        return pickupDates       

    def api_get(self, path="", query=None):
        response = requests.get(REST_API_URL + path)
        response.raise_for_status()
        return json.loads(response.content.decode("UTF-8"))

    def api_post(self, path="", data=None):
        response = requests.post(REST_API_URL + path, headers=self.headers, json=data)
        response.raise_for_status()

        return json.loads(response.content.decode("UTF-8"))


    @property
    def headers(self):
        headers = {"Content-Type": "application/json", "apiKey": self._apiKey}

        if self._okta_access_token is not None:
            headers["oktaToken"] = self._okta_access_token

        return headers
