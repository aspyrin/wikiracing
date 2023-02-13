# wikiracing
This Python application solves the problem of how to get from one Wikipedia article to another article with the  minimum number of transitions.
The function wikiracing.py/WikiRacer()/find_path takes two article names as parameters and returns a list of page 
names  through which it can be reached, or an empty list if such a path could not be found.
Example:
(‘Дружба’, ‘Рим’) -> [‘Дружба’, ‘Якопо Понтормо’, ‘Рим’]

# Conditions:
 - We are looking for articles only on the Ukrainian Wikipedia 
(settings.py/source_link, , by default = 'https://uk.wikipedia.org/wiki/')
 - Technical articles of this type:
   - https://uk.wikipedia.org/wiki/%D0%92%D1%96%D0%BA%D1%96%D0%BF%D0%B5%D0%B4%D1%96%D1%8F:%D0%92%D1%96%D0%B9%D0%BD%D0%B0/%D0%A0%D0%B5%D1%81%D1%83%D1%80%D1%81%D0%B8
   - or https://uk.wikipedia.org/wiki/%D0%9E%D0%B1%D0%B3%D0%BE%D0%B2%D0%BE%D1%80%D0%B5%D0%BD%D0%BD%D1%8F:%D0%A8%D0%B5%D0%B2%D1%87%D0%B5%D0%BD%D0%BA%D0%BE_%D0%A2%D0%B0%D1%80%D0%B0%D1%81_%D0%93%D1%80%D0%B8%D0%B3%D0%BE%D1%80%D0%BE%D0%B2%D0%B8%D1%87 
no parse
 - The frequency of requests is limited (parameter - settings.py/requests_per_minute, by default = 100). 
This is controlled by a function wikiracing.py/WikiRacer()/_request_limiter
 - In parser function implemented error handling and retry for requests:
   - except ConnectionError
     - retry N attempts (where N is parameter: settings.py/connection_retries, by default = 20) 
     with increments delay D (where D parameter: settings.py/connection_delay_if_error, by default = 60 sec)
   - except HTTPError 
     - if response.status_code == 404 -> the page set status PARSED_NO_SUCH_ARTICLE
     - if response.status_code in [429, 500, 502, 503, 504] -> 
     retry N attempts (where N is parameter: settings.py/response_retries, by default = 10) 
     with increments delay D (where D parameter: settings.py/response_delay_if_error, by default = 30 sec)
 - The parser function take only the first 200 links on each page 
(parameter: settings.py/links_per_page, by default = 200)
 - The received information about links from the page is stored in the postgres database running in the docker container
Private settings of postgresql are migrated to .env file. Also, in docker-compose file added container pgadmin service. 
Postgresql data is stored in volume pg_data in a root of project.
 - In the next runs, the function uses database connections to avoid making the same queries twice
   The function can work in two modes: 
     - if a route search solution has already been successfully found before, 
   the function immediately returns the saved search chain of route. 
   *This option can be enabled or disabled by parameter: settings.py/return_route_if_it_exists_in_db, by default = True.
   *In some unit tests this parameter is forcibly set to the False position at the level of the WikiRacer() class.
     - if this is the first search for this route, or the search was not successful before, 
   then the function searches from the beginning, but still uses the pages and links between them previously saved 
   in the database.
 - On the database, which will be filled after several runs, you can perform queries that look for 
(at file queries.sql):
   - Task 1. Top 5 most popular articles (those with the most links to themselves)
   - Task 2. Top 5 articles with the most links to other articles 
   - Task 3. For a given article, find the average number of descendants of the second level
   - Task 4. A query with the -N parameter returns up to five traversal paths of length N. 
   The pages in the path is not repeated.
   *NOTE: Task 4 was implemented on the basis of four functions (get_next_generation_chains(), 
   get_routes_with_n_depth_by_start_page_limit_count(), get_all_valid_pages_order_random(), 
   get_routes_with_n_depth_limit_count() - main function)
   These functions need to be created. 
   To get the result, you need to call main function get_routes_with_n_depth_limit_count()
   Example, SELECT * FROM get_routes_with_n_depth_limit_count(5, 5); 
   where first parameter(int) - N (the depth of routes), second parameter(int) - get rows limit
 - The list of libraries to be installed look at the requirements.txt file
 - Characteristics of the local machine on which the application and tests were performed:
   - Hard: DELL Latitude-5520, 11th Gen Intel® Core™ i5-1145G7 @ 2.60GHz × 8, RAM 15,4 GB
   - OS: Ubuntu 20.04.5 LTS (64 bit)
   - env: Python 3.10

# Some implementation features
 - Аll interactions with the database are placed in a separate module layer db_context.py
   - class DB() - implements DB connection functions, and also functions: query, commit, close
   - class PageStatus(Enum) - describes enum type with wiki-page statuses
   - class WikiPage() - implements the creation of wiki-page objects 
   and their properties and methods of interaction with the database
   - class Route() - implements the creation of route objects, their properties and methods of interaction with the DB
   - other static functions
    Transferring all the code of interaction with the DB, allows to unload and make the code in other Python functions 
    more compact and "clean". 
    In module wikiracing.py classes Node() and CurrentRoute() inherits from classes WikiPage() and Route(), 
    while preserving all methods of interaction with the DB and expanding with new methods and properties.

 - The local method _request_limiter in wikiracing.py/WikiRacer() is called only when application need run request.
   Each call of this function calculate the current number of requests per minute, compares it with the given settings 
   and returns an answer whether it is possible to make the next request now.

 - The local method __page_parsing in wikiracing.py/WikiRacer() accepts a wiki page object as an input argument, 
   and if it has a NOT_PARSED status (previously not parsed), the function starts the parsing procedure.
   this function do next operations:
      -if page not in db -> add it
      -if page has no linked pages in db (status == NOT_PARSED)
         -> parsing page
          -if link title not in ignore_list_patterns (ignore_list_patterns.py/check_pattern_in_title()):
           -if no more then links_per_page (parameter: settings.py/links_per_page):
            -> add new pages to DB (links from wiki page)
            -> add links 'parent-child' to db (the table 'links')
          -if link return exception (404):
            -> set page status PARSED_NO_SUCH_ARTICLE
          -else:
            -> set page status PARSED_CAN_BE_USED

 - During the operation of the application, a log can be output to the terminal console. 
   The WikiRacer()/print_log_msg() function is responsible for this.
   *This option can be enabled or disabled by parameter: settings.py/display_log, by default = True.
   *In unit tests this parameter is forcibly set to the False position at the level of the WikiRacer() class.

 - The main function wikiracing.py/WikiRacer()/find_path accepts two parameters (start, finish) and has the following 
   algorithm:
   - validation start not equals finish
     -if they are equal:
       -> return StartAndFinishEqualityException
   - validation start page (pars on wiki site)
     -if it is wrong:
       -> return StartPageTitleException
   - validation finish page (pars on wiki site)
     -if it is wrong:
       -> return FinishPageTitleException
   - check current route is exists in DB
     -if is exists and return_route_if_it_exists_in_db == True:
      -> return chain from DB
   - start of the search route in two cycles: 
     - while cycle
        in this cycle we are increment generation (start page = 0 generation, 
        and then each next generation of children is a generation +1)
        exit condition:
            or current generation == settings.py/max_links_in_route
            or we found the finish page among the children
        - for cycle
         in this cycle we are loop through all valid children (nodes) in the current generation from all parents 
         (nodes) in previous generation (current generation -1)
         Each new node we add to the list of all pages viewed. This list is a property of the current_route object.
         If current node is exists in the list of all pages viewed, we not append it, and mark this node 'is_dead_end'.
         Then we try to parse this node and add to DB all links from this page.
         Each node stores inside itself information about its parent-node and the path from itself to the start node.
         So when we encounter a node in the loop that is the finish, we immediately have an idea of the path from 
         this node to the start. Meeting with such a node is the condition for exiting the for cycle.
