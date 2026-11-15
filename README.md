Location Guesser (Linz Edition)

A python-based application which can help player find hidden location based on few clues. Using graph theories, OpenStreetMap data to narrow down the map down to "Final Possible Area."

🚀 Features
Custom Speed Calibration: Calibrate the routing engine to match your exact walking speed by timing a known route.

Geospatial Filtering: Instantly restrict the search area to specific OpenStreetMap object types (e.g., residential buildings, parks, supermarkets).

Walking Isochrones: Calculate complex reachability polygons based on minimum and maximum walking minutes from specific reference addresses.

Proximity to Groceries: Automatically calculates distance radiuses to the nearest grocery stores across the entire city.

Interactive Map Generation: Outputs a standalone linz_game_map.html using Folium and GeoPandas, complete with a custom JavaScript button to instantly isolate the final intersecting search area.

🛠️ Tech Stack
Python 3.8+

OSMnx & NetworkX: For downloading OpenStreetMap street networks and performing shortest-path routing computations.

GeoPandas & Shapely: For handling spatial data, buffering geometry, and calculating polygon intersections.

Folium: For generating the interactive web map.
