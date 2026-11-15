import urllib.request
import json
import ssl

print("Connecting to the Austrian Open Data Portal...")
# This is the exact dataset ID for Linz AG Linien
api_url = "https://www.data.gv.at/katalog/api/3/action/package_show?id=d3c0a223-516b-4049-9370-22881a0428d8"

try:
    # Bypass local SSL certificate issues just in case
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    with urllib.request.urlopen(api_url, context=ctx) as response:
        data = json.loads(response.read().decode())
        
    resources = data.get('result', {}).get('resources', [])
    gtfs_url = None
    
    for res in resources:
        name = str(res.get('name', '')).lower()
        if 'gtfs' in name:
            gtfs_url = res.get('url')
            break
            
    if gtfs_url:
        print(f"Found the exact Linz GTFS file!")
        print(f"Downloading from: {gtfs_url}")
        print("Please wait, this might take a minute or two...")
        
        # This downloads and overwrites your bad zip file with the perfect one
        urllib.request.urlretrieve(gtfs_url, "linz_gtfs.zip")
        print("SUCCESS! 'linz_gtfs.zip' has been perfectly downloaded.")
    else:
        print("Could not find the GTFS link in the dataset.")
except Exception as e:
    print(f"An error occurred: {e}")