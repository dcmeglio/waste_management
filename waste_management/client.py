from datetime import datetime, timedelta
import re
import time
import json
import jwt

import requests

from .const import (
    API_KEY_AUTHENTICATION,
    API_KEY_CUSTOMER_SERVICES,
    API_KEY_HOLIDAYS_USER_BY_ADDRESS,
    API_KEY_USER_ACCOUNTS,
    REST_API_URL,
)
from .Entities import AccountInfo, Service


class WMClient:
    def __init__(self, email, password):
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
        self._holiday_regex = re.compile("(\d{1,2}/\d{1,2}(?:/\d{2,4})?)")
        self._delay_regex = re.compile("(\d+)(?: day)? delay")

    def _string_escape(self, input: str, encoding="utf-8"):
        return (
            input.encode("latin1")
            .decode("unicode-escape")
            .encode("latin1")
            .decode(encoding)
        )

    def authenticate(self):
        self._apiKey = API_KEY_AUTHENTICATION
        data = self.api_post(
            "user/authenticate",
            {"username": self.email, "password": self.password, "locale": "en_US"},
        )
        response_data = data["data"]

        self._session_token = response_data["sessionToken"]
        self._access_token = response_data["access_token"]
        self._refresh_token = response_data["refresh_token"]
        self._id_token = response_data["id_token"]
        self._user_id = response_data["id"]
        self._token_expires_time = time.time() + response_data["expires_in"]
        decoded_jwt = jwt.decode(
            response_data["access_token"], options={"verify_signature": False}
        )
        self._client_id = decoded_jwt["cid"]
        self._issuer = decoded_jwt["iss"]
        return data

    def okta_authorize(self):
        # get from access token issuer
        response = requests.get(
            self._issuer + "/v1/authorize",
            {
                "client_id": self._client_id,
                "nonce": "x",
                "prompt": "none",
                "response_mode": "okta_post_message",
                "response_type": "token",
                "state": "x",
                "scope": "openid email offline_access",
                "redirect_uri": "https://www.wm.com",
                "sessionToken": self._session_token,
            },
        )
        response.raise_for_status()
        result = re.search("access_token\s*=\s*'(.+?)'", response.text, re.MULTILINE)
        self._okta_access_token = self._string_escape(result.group(1))

    def get_accounts(self):
        self._apiKey = API_KEY_USER_ACCOUNTS

        response = requests.get(
            REST_API_URL + f"authorize/user/{self._user_id}/accounts",
            headers=self.headers,
            params={"timestamp": time.time() * 1000, "lang": "en_US"},
        )
        response.raise_for_status()

        jsonData = json.loads(response.content.decode("UTF-8"))

        results = []
        for acct in jsonData["data"]["linkedAccounts"]:
            results.append(AccountInfo(acct))
        return results

    def get_services(self, account_id):
        self._apiKey = API_KEY_CUSTOMER_SERVICES

        response = requests.get(
            REST_API_URL + f"account/{account_id}/services",
            headers=self.headers,
            params={
                "lang": "en_US",
                "serviceChangeEligibility": "Y",
                "userId": self._user_id,
            },
        )
        response.raise_for_status()

        jsonData = json.loads(response.content.decode("UTF-8"))
        results = []
        for svc in jsonData["services"]:
            results.append(Service(svc))

        return results

    def get_service_pickup(self, account_id, service_id):
        self._apiKey = API_KEY_CUSTOMER_SERVICES

        response = requests.get(
            REST_API_URL + f"account/{account_id}/service/{service_id}/pickupinfo",
            headers=self.headers,
            params={"lang": "en_US", "checkAlerts": "Y", "userId": self._user_id},
        )
        response.raise_for_status()

        jsonData = json.loads(response.content.decode("UTF-8"))

        upcoming_holiday_date = self.__get_holiday_delay_date(jsonData)
        holiday_info = None
        if upcoming_holiday_date is not None:
            holiday_info = self.get_holidays(account_id)

        pickupDates = []
        for dateStr in jsonData["pickupScheduleInfo"]["pickupDates"]:
            date = datetime.strptime(dateStr, "%m-%d-%Y")
            if date == upcoming_holiday_date and date in holiday_info.keys():
                date = holiday_info[date]
            pickupDates.append(date)

        return pickupDates

    def get_holidays(self, account_id):
        self._apiKey = API_KEY_HOLIDAYS_USER_BY_ADDRESS

        response = requests.get(
            REST_API_URL + f"user/{self._user_id}/account/{account_id}/holidays",
            headers=self.headers,
            params={"lang": "en_US", "type": "upcoming"},
        )
        response.raise_for_status()

        jsonData = json.loads(response.content.decode("UTF-8"))

        holidays = {}

        if "holidayData" in jsonData:
            for holiday in jsonData["holidayData"]:
                holiday_message = holiday["holidayHours"]
                holidays.update(self.__parse_holiday_impacted_dates(holiday_message))
        return holidays

    def api_get(self, path="", query=None):
        response = requests.get(REST_API_URL + path)
        response.raise_for_status()
        return json.loads(response.content.decode("UTF-8"))

    def api_post(self, path="", data=None):
        response = requests.post(REST_API_URL + path, headers=self.headers, json=data)
        response.raise_for_status()

        return json.loads(response.content.decode("UTF-8"))

    def __get_holiday_delay_date(self, jsonData):
        if "pickupDayInfo" in jsonData:
            jsonNode = jsonData["pickupDayInfo"]
            if "message" in jsonNode and jsonNode["message"] is not None:
                # The only way to tell if the date is impacted by a holiday is via the message string
                if "HOLIDAY" in jsonNode["message"].upper():
                    date_str = jsonNode["date"]
                    return datetime.strptime(date_str, "%m-%d-%Y")
        return None

    def __parse_holiday_impacted_dates(self, message):
        """The API returns a text string that tells you about impacted dates. For example:
        Due to the Thanksgiving Day holiday, your scheduled service will not be delayed
        except for 11/24, it will be on a 1 day delay excluding city of Allentown (no delay).
        11/25 service will be on 1 day delay except for city of Allentown will be serviced
        on the next pickup day.

        So there is a lot to try to figure out here. First it tells us dates in the string that are impacted
        in a pretty imprecise way, just a text string (no year) and tells us how many days to adjust. Second,
        it tells us that certain cities are not impacted. This does not yet attempt to determine if you're in
        an overriden city, but it does attempt to parse the text to determine if there is a delay.
        """
        impacted_dates = {}
        # Look for anything that looks like a date, basically NN/NN and find them within the text.
        for match in self._holiday_regex.finditer(message):
            impacted_date_str = match.group(1)
            month_day = datetime.strptime(impacted_date_str, "%m/%d")
            impacted_date = month_day.replace(year=datetime.today().year)
            if impacted_date < datetime.today():
                impacted_date = month_day.replace(year=datetime.today().year + 1)

            impacted_dates[impacted_date] = match.span()

        # Now that we have things that look like dates, we want to check the text after those dates
        # to try to look for delays.
        date_keys = list(impacted_dates.keys())
        str_len = len(message)
        for i in range(0, len(date_keys)):
            date = date_keys[i]
            current_date_span = impacted_dates[date]
            (_, start) = current_date_span
            if i < len(date_keys) - 1:
                (end, _) = impacted_dates[date_keys[i + 1]]
            else:
                end = str_len
            slice = message[start:end]

            impacted_dates[date_keys[i]] = date_keys[i]

            if slice is not None:
                delay_match = self._delay_regex.search(slice)
                groups = delay_match.groups()
                if len(groups) > 0:
                    delay = groups[0]
                    impacted_dates[date_keys[i]] = date_keys[i] + timedelta(
                        days=int(delay)
                    )

        return impacted_dates

    @property
    def headers(self):
        headers = {"Content-Type": "application/json", "apiKey": self._apiKey}

        if self._okta_access_token is not None:
            headers["oktaToken"] = self._okta_access_token

        return headers
