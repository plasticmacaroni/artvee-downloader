import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import time
import os
import re
import yaml

BASE_URL = 'https://artvee.com'

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def login(session):
    login_url = BASE_URL + '/login'  # Update with the actual login path
    
        # Fetch the login page first to get the nonce
    response = session.get(login_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    nonce = soup.find('input', {'name': 'ihc_login_nonce'})['value']

    # Create the config.yaml file if it doesn't exist
    if not os.path.exists('config.yaml'):
        with open('config.yaml', 'w') as file:
            yaml.dump({}, file)

    # Load the config.yaml file
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    # First, check if it's empty, and ask for user input if so
    if not config['username']:
        config['username'] = input("Enter your username: ")
    if not config['password']:
        config['password'] = input("Enter your password: ")
    # Notify the user these can be changed in the config.yaml file
    if not config['username'] or not config['password']:
        print("You must enter a username and password in the config.yaml file, which you can manually edit the config.yaml file or run this script again to enter them.")
        exit()

    # Update the file with any new user input
    with open('config.yaml', 'w') as file:
        yaml.dump(config, file)

    data = {
        'log': config['username'],
        'pwd': config['password'],
        'ihcaction': 'login',
        'ihc_login_nonce': nonce
    }
    response = session.post(login_url, data=data)
    # Verifying login by printing content of the page after login attempt
    if config["username"] in response.text:  # Update this with an actual keyword or phrase from a successful login
        print("Successfully logged in!")
    else:
        print("Login failed!")
        print(response.text)

    print("Logged in successfully:", response.ok)

def sanitize_filename(filename):
    # Trim whitespace from either side
    filename = filename.strip()
    # Remove any non-alphanumeric characters (except dashes, underscores, and spaces)
    sanitized = re.sub(r'[^a-zA-Z0-9 _-]', '', filename)
    # Replace dashes and underscores with spaces
    sanitized = sanitized.replace('-', ' ').replace('_', ' ')
    # Capitalize every word
    sanitized = sanitized.title()
    return sanitized
    
def download_photos_from_collection_page(session, collection_url, page=1):
    if page > 1 and not collection_url.find("/" + str(page) + "/"):
        print("We were sent to page 1 while paginating... everything downloaded from collection!")

    lookup_url = collection_url
    if page > 1:
        lookup_url += str(page)
    print("Direct link:", lookup_url)

    response = session.get(lookup_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    # get the title    
    title_elem = soup.select_one('div.si-title-wrapper > h1.entry-title.woodmart-font-weight-900')
    if title_elem:
        title_text = title_elem.text.strip()  # This will hold the text "Botanical"
    else:
        print('Failed to find title element')

    # Check if we're on the last page of a collection (or for an unfound collection)
    end_paginate_elem = soup.select_one('h4.woodmart-title-container.title')
    if end_paginate_elem and end_paginate_elem.text.strip() == '404':
        print('Empty page of collection encountered. Stopping execution.')
        return
    
    print("Scraping page number", page)

    elements = soup.select('div.snax-collection-item')
    if len(elements) < 1:
        print("Couldn't find any elements on page", str(page) + ".")
        return
    for el in elements:
        # DL_link
        DL_link = el.select_one('.product-image-link[data-url]')
        # Get the artist name
        artist_elem = el.select_one('div.woodmart-product-brands-links > a')
        if artist_elem:
            artist_name = artist_elem.text.strip()
        else:
            print('Artist element not found')

        ajax_url = "https://artvee.com/erica"  # assuming this is the correct URL
        mid = DL_link.get('data-id')
        data_url = DL_link.get('data-url')

        # Data to be sent in the AJAX request
        data = {
            'id': mid,
            'action': 'woodmart_quick_view2',
        }

        # Mimic the AJAX request
        ajax_response = session.get(ajax_url, params=data)
        ajax_response.raise_for_status()

        # Check if the response is JSON, and if so, extract the 'flink' field
        response_json = ajax_response.json()
        flink = response_json.get('flink')
        if flink:
            # Create the images and collection folder if it doesn't exist
            os.makedirs('images', exist_ok=True)
            os.makedirs('images/' + sanitize_filename(str(title_text) + " Collection"), exist_ok=True)
            
            # Determine the filename from the URL (excluding the query parameters)
            filename = os.path.basename(flink.split('?')[0])
            
            # Sanitize the data_url for use as a filename
            filename = sanitize_filename(data_url)
            filename = filename.lower().replace("dl", "", 1)

            # Check if the file already exists
            image_filepath = os.path.join('images/' + sanitize_filename(str(title_text) + " Collection"), sanitize_filename(artist_name) + " - " + sanitize_filename(filename) + ".jpg")
            print("Downloading from page", str(page) + ":\n\t" + 'Images / ' + sanitize_filename(str(title_text) + " Collection"), "/ " + sanitize_filename(artist_name) + " - " + sanitize_filename(filename) + ".jpg")
            if os.path.exists(image_filepath):
                print(f'\tImage {filename} already exists. Skipping download.')
                continue  # Skip to the next iteration of the loop

            # Make the request to download the image
            image_response = requests.get(flink)
            image_response.raise_for_status()  # Check for a valid response

            # Save the image to the 'images' directory, and log any errors
            try:
                with open(image_filepath, 'wb') as file:
                    file.write(image_response.content)
            except Exception as e:
                print(f"Error writing file {image_filepath}: {e}")
                exit()

        else:
            print('No flink field in the JSON response')
        time.sleep(2)
    print("Fetching page number", page+1)
    download_photos_from_collection_page(session, collection_url, page+1)


def fetch_artwork_data(session, url):
    download_link = None
    artist_name = None
    title = None

    response = session.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Update these selectors based on the structure of the website
    download_link_elem = soup.select_one('a.prem-link')
    artist_name_elem = soup.select_one('div.woodmart-product-brands-links > a')
    title_elem = soup.select_one('h1.product_title.entry-title > a')

    try:
        if download_link_elem:
            download_link = download_link_elem['src']  # or ['href'] depending on the element type

        if artist_name_elem:
            artist_name = artist_name_elem.text.strip()

        if title_elem:
            title = title_elem.text.strip()

        if not download_link:
            print(f"Failed to find download link for {url}")

        if not artist_name or not title:
            print(f"Failed to find artist or title for {url}")
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")

    return download_link, artist_name, title


def download_and_rename(session, download_link, artist_name, title):
    response = session.get(download_link, stream=True)
    
    # Handle file naming
    filename = f"{artist_name} - {title}.jpg"  # Adjust the file extension if needed
    sanitized_filename = ''.join(c for c in filename if c.isalnum() or c in (' ', '.', '-')).rstrip()
    print("Attempting to download from:", download_link)
    with open(sanitized_filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def main():
    with requests_retry_session() as session:
        # Log into the website
        login(session)
        
        # Input the URL of your collection
        collection_url = input("Enter the URL of your collection, like https://artvee.com/s_collection/666233/: ")
        if not collection_url:
            print("You must enter a URL.")
            exit()
        download_photos_from_collection_page(session, collection_url)

if __name__ == "__main__":
    main()
