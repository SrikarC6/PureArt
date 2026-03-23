import requests

def search_artwork(search_type, name):
    album_link = "https://itunes.apple.com/search?term=ALBUMNAME&entity=album&attribute=albumTerm&limit=25"
    song_link = "https://itunes.apple.com/search?term=SONGNAME&entity=song&attribute=songTerm&limit=25"
    artist_link = "https://itunes.apple.com/search?term=ARTISTNAME&entity=album&attribute=artistTerm&limit=25"
    all_results = []
    name = name.replace(' ', '+')

    if search_type == 'album':
        album_link = album_link.replace("ALBUMNAME", name)
        album_requests_dict = requests.get(album_link).json()
        results = album_requests_dict['results']

    elif search_type == 'song':
        song_link = song_link.replace("SONGNAME", name)
        song_requests_dict = requests.get(song_link).json()
        results = song_requests_dict['results']

    elif search_type == 'artist':
        artist_link = artist_link.replace("ARTISTNAME", name)
        artist_requests_dict = requests.get(artist_link).json()
        results = artist_requests_dict['results']

    else:
        raise ValueError("Invalid search type. Please enter album, song, or artist.")

    for item in results:
        result_info = {}
        result_info['artist_name'] = item['artistName']
        result_info['release_date'] = item['releaseDate']
        result_info['artwork_link'] = item['artworkUrl100'].replace('100x100bb', '10000x10000bb')
        all_results.append(result_info)

    return all_results