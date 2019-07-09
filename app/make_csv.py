import json

with open("app\\20190709-ALLDB.json", "r") as json_file:
    dbs = json.load(json_file)

# Create CSV records and compress out duplicates
dbdict = {}
for my_dict in dbs:
    if my_dict:
        for key, value in my_dict.items():
            desc = '"'+value["desc"]+'"'
            name = '"'+value["name"]+'"'
            dbtype = '"'+value["type"]+'"'
            prot = '"'+value["prot"]+'"'
            if dbtype != "group":
                dbstate = '"'+key[:2]+'"'
            else:
                dbstate = '""'
            rec = ",".join([dbstate, key, desc, name, dbtype, prot])
            dbdict[key] = rec

with open("app\\20190709-ALLDB.csv", "w") as csv_file:
    for dbkey, csv_rec in dbdict.items():
        csv_file.write(csv_rec+"\n")
