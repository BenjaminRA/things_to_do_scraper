import json
import os

final = []

google_places_id = {}

folders = os.listdir('./Final/Temp')

for folder in folders:
    print(folder)
    repeated = 0

    # check if file exists
    if os.path.exists("Final/Temp/" + folder + "/adminsplaces_news_0.json"):
        index = 0
        while os.path.exists("Final/Temp/" + folder + "/adminsplaces_news_" + str(index) + ".json"):
            with open("Final/Temp/" + folder + "/adminsplaces_news_" + str(index) + ".json", encoding="utf-8") as places_raw:
                places = json.load(places_raw)
                for place in places:
                    if place['googlePlaceId'] not in google_places_id:
                        final.append(place)
                        google_places_id[place['googlePlaceId']] = True

            index += 1

    else:
        with open("Final/Temp/" + folder + "/adminsplaces_news.json", encoding="utf-8") as places_raw:
            places = json.load(places_raw)
            for place in places:
                if place['googlePlaceId'] in google_places_id:
                    repeated += 1
                    continue

                final.append(place)
                google_places_id[place['googlePlaceId']] = True

    print(f"Repeated: {repeated}")
with open("Final/adminsplaces.json", "w") as outfile:
    json.dump(final, outfile)
