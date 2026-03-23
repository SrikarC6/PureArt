import requests

def search_artwork(search_type, name):
    album_link = "https://itunes.apple.com/search?term=ALBUMNAME&entity=album&attribute=albumTerm&limit=25"
    song_link = "https://itunes.apple.com/search?term=SONGNAME&entity=song&attribute=songTerm&limit=25"
    artist_link = "https://itunes.apple.com/search?term=ARTISTNAME&entity=album&attribute=artistTerm&limit=25"
    artwork_links = []
    name = name.replace(' ', '+')

    if search_type == 'album':
        album_link = album_link.replace("ALBUMNAME", name)
        album_requests_dict = requests.get(album_link).json()
        album_results = album_requests_dict['results']
    
        for album in album_results:
            album['artworkUrl100'] = album['artworkUrl100'].replace('100x100bb', '10000x10000bb')
            artwork_links.append(album['artworkUrl100'])

    elif search_type == 'song':
        song_link = song_link.replace("SONGNAME", name)
        song_requests_dict = requests.get(song_link).json()
        song_results = song_requests_dict['results']
    
        for song in song_results:
            song['artworkUrl100'] = song['artworkUrl100'].replace('100x100bb', '10000x10000bb')
            artwork_links.append(song['artworkUrl100'])

    elif search_type == 'artist':
        artist_link = artist_link.replace("ARTISTNAME", name)
        artist_requests_dict = requests.get(artist_link).json()
        artist_results = artist_requests_dict['results']
    
        for album in artist_results:
            album['artworkUrl100'] = album['artworkUrl100'].replace('100x100bb', '10000x10000bb')
            artwork_links.append(album['artworkUrl100'])

    else:
        raise ValueError("Invalid search type. Please enter album, song, or artist.")
        
    return artwork_links