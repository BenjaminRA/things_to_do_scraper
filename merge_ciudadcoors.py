import json
import os

final = []

folders = os.listdir('./Final/Temp')

for folder in folders:
    print(folder)

    with open("Final/Temp/" + folder + "/ciudadcoors_news.json", encoding="utf-8") as places_raw:
        places = json.load(places_raw)
        for place in places:
            final.append(place)


with open("Final/ciudadcoors.json", "w") as outfile:
    json.dump(final, outfile)
