from jarbas_hive_mind.database import ClientDatabase

name = "JarbasDeltaChatBridge"
access_key = "erpDerPerrDurHUrRRRRR"
mail = "deltachat@hivemind.com"


with ClientDatabase() as db:
    db.add_client(name, mail, access_key)
