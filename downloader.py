import os
import pickle
import osmnx as ox
import networkx as nx
import geopandas as gpd
import folium  # <--- Add this new import here!
from shapely.ops import unary_union

GRAPH_FILENAME = "linz_ready_data.pkl"

def build_full_graph():
    place = "Linz, Upper Austria, Austria"
    G_walk = ox.graph_from_place(place, network_type="walk")
    G_walk = ox.project_graph(G_walk)

    WALK_SPEED_M_MIN = 80.0 
    G_walk.graph["walk_speed"] = WALK_SPEED_M_MIN
    for u, v, k, data in G_walk.edges(keys=True, data=True):
        data["travel_time"] = data["length"] / WALK_SPEED_M_MIN
    
    return G_walk

def get_ready_data():
    if os.path.exists(GRAPH_FILENAME):
        print("Loading ready data from disk...")
        with open(GRAPH_FILENAME, "rb") as f:
            G_ready = pickle.load(f)
        return G_ready
    else:
        print("Building data from scratch (this may take a minute)...")
        G_ready = build_full_graph()
        with open(GRAPH_FILENAME, "wb") as f:
            pickle.dump(G_ready, f)
        return G_ready

def get_node_for_address(G, address_str):
    try:
        coords = ox.geocode(f"{address_str}, Linz, Austria")
        pt = gpd.GeoSeries([gpd.points_from_xy([coords[1]], [coords[0]])[0]], crs="EPSG:4326").to_crs(G.graph["crs"]).iloc[0]
        return ox.nearest_nodes(G, pt.x, pt.y)
    except Exception as e:
        print(f"  [!] Could not find address '{address_str}'. Error: {e}")
        return None

def calibrate_speed(G):
    print("\n--- STEP 1: CALIBRATE WALKING SPEED ---")
    start_addr = input("Enter a start address (e.g., Altenberger Straße 69): ")
    end_addr = input("Enter a destination address (e.g., Hauptstraße 54): ")
    
    try:
        mins = float(input(f"Minutes to walk from {start_addr} to {end_addr}? "))
        start_node = get_node_for_address(G, start_addr)
        end_node = get_node_for_address(G, end_addr)
        
        if start_node and end_node:
            dist_meters = nx.shortest_path_length(G, start_node, end_node, weight="length")
            custom_speed = dist_meters / mins
            G.graph["walk_speed"] = custom_speed
            for u, v, k, data in G.edges(keys=True, data=True):
                data["travel_time"] = data["length"] / custom_speed
            print(f"  -> Calibrated! Your speed: {custom_speed:.0f} m/min.")
        else:
            print("  [!] Failed. Using default speed (80 m/min).")
    except ValueError:
        print("  [!] Invalid number. Using default speed.")
        
    return G

def get_walking_isochrone(G, origin_node, minutes, edge_buffer=25):
    subgraph = nx.ego_graph(G, origin_node, radius=minutes, distance="travel_time")
    if "VIRTUAL_SOURCE" in subgraph:
        subgraph.remove_node("VIRTUAL_SOURCE")
        
    if len(subgraph.nodes) < 2:
        valid_node = list(subgraph.nodes)[0] if subgraph.nodes else origin_node
        point = G.nodes[valid_node]
        return gpd.points_from_xy([point["x"]], [point["y"]])[0].buffer(edge_buffer)

    nodes, edges = ox.graph_to_gdfs(subgraph)
    return unary_union(edges.geometry.buffer(edge_buffer))

def get_address_ring(G, address_node, min_time, max_time):
    max_poly = get_walking_isochrone(G, address_node, minutes=max_time)
    if min_time > 0:
        min_poly = get_walking_isochrone(G, address_node, minutes=min_time)
        return max_poly.difference(min_poly)
    return max_poly

# ==========================================
# MAIN INTERACTIVE SCRIPT
# ==========================================
if __name__ == "__main__":
    G_walk = get_ready_data()
    G_walk = calibrate_speed(G_walk)

    linz_boundary = ox.geocode_to_gdf("Linz, Upper Austria, Austria").to_crs(G_walk.graph["crs"]).geometry.iloc[0]
    final_area = linz_boundary
    map_layers = []
    
    # Store grocery locations lazily so we only download them if requested
    grocery_points = None

    print("\n--- STEP 2: TARGET LOCATION TYPE ---")
    obj_type = input("What kind of object is the person hiding at? (e.g., place to live, park, supermarket, or 'none'): ").strip().lower()
    
    if obj_type != 'none':
        print(f"Downloading all '{obj_type}' locations in Linz... please wait.")
        try:
            tags = {'amenity': obj_type}
            if obj_type in ['park']: tags = {'leisure': 'park'}
            elif obj_type in ['supermarket', 'grocery']: tags = {'shop': ['supermarket', 'convenience', 'grocery']}
            elif obj_type in ['place to live', 'apartment', 'house']: tags = {'building': ['residential', 'apartments', 'house', 'detached', 'terrace']}
            
            pois = ox.features_from_place("Linz, Austria", tags=tags).to_crs(G_walk.graph["crs"])
            poi_poly = unary_union(pois.geometry.centroid.buffer(20))
            
            final_area = final_area.intersection(poi_poly)
            map_layers.append({"Clue": f"Target Objects: {obj_type}", "geometry": final_area})
            print(f"  -> Map restricted to {obj_type}s.")
        except Exception as e:
            print(f"  [!] Could not filter by '{obj_type}'.")

    print("\n--- STEP 3: ENTER CLUES ---")
    clue_count = 1
    
    while True:
        print(f"\n[ Clue #{clue_count} ]")
        print("1. Walking distance from a specific address")
        print("2. Walking distance to the NEAREST grocery store")
        print("3. Done (Generate Map)")
        
        choice = input("Select clue type (1/2/3): ").strip()
        
        if choice == '3' or choice.lower() == 'done':
            break
            
        try:
            if choice == '1':
                addr = input("  Enter reference address/stop: ").strip()
                addr_node = get_node_for_address(G_walk, addr)
                if not addr_node: 
                    continue
                    
                min_t = float(input("  Minimum minutes walking (enter 0 if exact/less): "))
                max_t = float(input("  Maximum minutes walking: "))
                
                print("  -> Calculating walking radius...")
                clue_poly = get_address_ring(G_walk, addr_node, min_time=min_t, max_time=max_t)
                clue_name = f"Clue {clue_count}: {min_t}-{max_t}m from {addr}"
                
            elif choice == '2':
                if grocery_points is None:
                    print("  -> Downloading grocery store locations (this only happens once)...")
                    tags = {'shop': ['supermarket', 'convenience', 'grocery']}
                    groceries = ox.features_from_place("Linz, Austria", tags=tags).to_crs(G_walk.graph["crs"])
                    grocery_points = groceries.geometry.centroid
                
                min_t = float(input("  Min minutes to nearest grocery store (enter 0 if exact/less): "))
                max_t = float(input("  Max minutes to nearest grocery store: "))
                
                print("  -> Calculating unified radius around all supermarkets...")
                # Convert minutes to meters based on your calibrated walking speed
                walk_speed = G_walk.graph.get("walk_speed", 80.0)
                max_dist = max_t * walk_speed
                min_dist = min_t * walk_speed
                
                max_poly = unary_union(grocery_points.buffer(max_dist))
                if min_t > 0:
                    min_poly = unary_union(grocery_points.buffer(min_dist))
                    clue_poly = max_poly.difference(min_poly)
                else:
                    clue_poly = max_poly
                    
                clue_name = f"Clue {clue_count}: {min_t}-{max_t}m to nearest grocery"
                
            else:
                print("  [!] Invalid choice.")
                continue
            
            if clue_poly is not None:
                map_layers.append({"Clue": clue_name, "geometry": clue_poly})
                final_area = final_area.intersection(clue_poly)
                clue_count += 1
            
        except ValueError:
            print("  [!] Invalid input. Numbers only please.")

    print("\n--- STEP 4: GENERATING MAP ---")
    if map_layers:
        map_layers.append({"Clue": "FINAL POSSIBLE AREA", "geometry": final_area})
        
        # 1. Create the base map using the first clue
        first_layer = gpd.GeoDataFrame([map_layers[0]], crs=G_walk.graph["crs"])
        m = first_layer.explore(
            name=map_layers[0]["Clue"],
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            style_kwds={"fillOpacity": 0.3, "weight": 2, "color": "blue"}
        )
        
        # 2. Add all the other clues layer-by-layer so they get their own checkboxes
        for layer in map_layers[1:]:
            gdf = gpd.GeoDataFrame([layer], crs=G_walk.graph["crs"])
            
            # Make the final area visually pop out in red
            if layer["Clue"] == "FINAL POSSIBLE AREA":
                gdf.explore(m=m, name=layer["Clue"], style_kwds={"fillOpacity": 0.6, "weight": 4, "color": "red"})
            else:
                gdf.explore(m=m, name=layer["Clue"], style_kwds={"fillOpacity": 0.3, "weight": 2, "color": "blue"})

        # Add the layer control panel so you can toggle them manually too
        folium.LayerControl().add_to(m)

        # 3. Inject the interactive button
        button_html = """
        <div style="position: fixed; top: 80px; left: 15px; z-index: 9999; 
                    background: white; padding: 10px 15px; border: 2px solid black; 
                    border-radius: 5px; cursor: pointer; font-family: sans-serif; font-weight: bold; 
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.5);"
             onclick="
             let inputs = document.querySelectorAll('.leaflet-control-layers-selector');
             let isIsolating = this.innerText.includes('Isolate');
             inputs.forEach(input => {
                 let label = input.closest('label');
                 let text = label ? label.textContent : '';
                 if (text && !text.includes('FINAL POSSIBLE AREA') && !text.includes('Esri')) {
                     if (isIsolating && input.checked) input.click();
                     else if (!isIsolating && !input.checked) input.click();
                 }
             });
             this.innerText = isIsolating ? 'Show All Clues' : 'Isolate Final Area';
             ">
            Isolate Final Area
        </div>
        """
        m.get_root().html.add_child(folium.Element(button_html))

        m.save("linz_game_map.html")
        print("Done! Open 'linz_game_map.html' in your browser.")
    else:
        print("No clues entered. Exiting.")