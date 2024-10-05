import os
from googleapiclient.discovery import build

API_KEY = 'YOUR_API_KEY'
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def youtube_search(query, max_results=5):
    youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=API_KEY)
    request = youtube.search().list(
        part='snippet',
        q=query,
        type='video',
        maxResults=max_results
    )
    response = request.execute()
    
    print(f"Top {max_results} results for '{query}':\n")
    for item in response['items']:
        video_title = item['snippet']['title']
        video_id = item['id']['videoId']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"Title: {video_title}")
        print(f"URL: {video_url}\n")

if __name__ == '__main__':
    youtube_search('Python programming')
