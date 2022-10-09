class AccountInfo():
    def __init__(self, json):
        address = json["serviceAddress"]
        self.name = f'{address["street"]} {address["city"]} {address["state"]}'
        self.id = json["custAccountId"]

class Service():
    def __init__(self, json):
        self.id = json["serviceId"]
        self.name = json["serviceDescription"]