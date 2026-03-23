import tidalapi
import requests

session = tidalapi.Session()
session.login_oath_simple()

def search_albums(query):
    results = session.search(query, query, models=[tidalapi.Album])
    return results['albums']
    
def download_art(album, filepath):
    url = album.image(1280)  # Pass in the resolution you want
    response = requests.get(url)
    with open(filepath, 'wb') as f:
        f.write(response.content)