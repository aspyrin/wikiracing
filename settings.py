import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# POSTGRES DB settings
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')

# PARSER SETTINGS
source_link = 'https://uk.wikipedia.org/wiki/'
requests_per_minute = 100
links_per_page = 200

# maximum route depth (number of links - N)
max_links_in_route = 4

# if connection error
connection_retries = 20  # number of retries
connection_delay_if_error = 60  # delay in seconds

# when response.status_code in [429, 500, 502, 503, 504]
response_retries = 10  # number of retries
response_delay_if_error = 30  # delay in seconds

# display log in console, when find path is running
display_log = True

# return the route if it was found earlier
return_route_if_it_exists_in_db = True
