import json


class AccountInfo():
    def __init__(self, json):
        address = json["serviceAddress"]
        self.name = f'{address["street"]} {address["city"]} {address["state"]}'
        self.id = json["custAccountId"]

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)

class Service():
    def __init__(self, json):
        self.id = json["serviceId"]
        self.name = json["serviceDescription"]

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)