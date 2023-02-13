import datetime
from time import sleep
from typing import List
import requests
from requests.exceptions import HTTPError, ConnectionError
from bs4 import BeautifulSoup

import settings
from db_context import PageStatus, WikiPage, Route
from db_context import (get_links_by_parent_page, clear_all_tables)
from ignore_list_patterns import check_pattern_in_title


# define Python user-defined exceptions
class StartAndFinishEqualityException(Exception):
    """
    Raised if start equals finish
    Attributes: start_page_title, finish_page_title
    """

    def __init__(self, start: str, finish: str):
        self.start = start
        self.finish = finish
        self.message = f"Start page {self.start} and Finish page {self.finish} cannot have the same name!"
        super().__init__(self.message)


class StartPageTitleException(Exception):
    """
    Raised when the StartPage is not exists in Wiki
    Attributes: start_page_title
    """

    def __init__(self, start: str, pars_status: int):
        self.start = start
        self.message = f"Start page: {self.start} has problems! ParsCode: {PageStatus(pars_status).name}."
        super().__init__(self.message)


class FinishPageTitleException(Exception):
    """
    Raised when the FinishPage is not exists in Wiki
    Attributes: finish_page_title
    """

    def __init__(self, finish: str, pars_status: int):
        self.finish = finish
        self.message = f"Finish page: {self.finish} has problems! ParsCode: {PageStatus(pars_status).name}."
        super().__init__(self.message)


# exceeding the maximum number of transitions
class ExceedingMaxLinksInRouteException(Exception):
    """
    Raised when the maximum number of links in a route is exceeded and the destination page is not found
    Attributes: max_links_in_route, cur_generation
    """

    def __init__(self):
        self.message = "The maximum number of hops in a route has been reached and no finish page has been found!"
        super().__init__(self.message)


class Node(WikiPage):
    """
    the class inherits all available properties and methods from the base class WikiPage,
    and also has additional properties and methods for use in the WikiRacer class
    """
    is_start: bool = False
    is_finish: bool = False
    is_dead_end: bool = False
    generation: int
    parent_node_title: str
    path_to_start: List[str] = []  # от старта до cur_node (включительно)

    def get_current_info(self) -> str:
        msg = f"""Info about Current Node:
        title: {self.title }, id: {self.id}, status: {PageStatus(self.status).name}, generation: {self.generation},
        is_start: {self.is_start}, is_dead_end: {self.is_dead_end}, is_finish: {self.is_finish},
        parent_node_title: {self.parent_node_title},
        path_to_start: {self.path_to_start},
        has_linked_pages_in_db: {self.has_linked_pages_in_db()}
        """
        return msg


class CurrentRoute(Route):
    """
    the class inherits all available properties and methods from the base class Route,
    and also has additional properties and methods for use in the WikiRacer class
    """
    success: bool = False
    cur_generation: int
    cur_node: Node
    all_nodes: List[Node] = []
    cur_path_to_start: List[str] = []

    def get_current_info(self) -> str:
        msg = f"""Info about route:
        success: {self.success}, cur_generation: {self.cur_generation}, 
        nodes_count (valid/all): {len(self.get_all_valid_node_titles())} / {len(self.all_nodes)},
        nodes_in_cur_generation: {self.get_all_valid_node_titles_by_generation(self.cur_generation)}
        """
        return msg

    def get_all_valid_node_titles(self) -> List[str]:
        """
        # получить все валидные узлы из текущей кучи маршрута (не из БД, а из CurrentRoute->all_nodes)
        :return: List[str]
        """
        result_list: List[str]
        result_list = []
        for node in self.all_nodes:
            if node.status == PageStatus.PARSED_CAN_BE_USED.value and not node.is_dead_end:
                result_list.append(node.title)
        return result_list

    def get_all_valid_node_titles_by_generation(self, generation: int) -> List[str]:
        """
        # получить имена всех валидных узлов из кучи текущего экземпляра маршрута
        (не из БД, а из CurrentRoute->all_nodes)
        с номером генерации, указанной в аргументе
        :param generation: int
        :return: List[str]
        """
        result_list: List[str]
        result_list = []
        for node in self.all_nodes:
            if node.status == PageStatus.PARSED_CAN_BE_USED.value \
                    and not node.is_dead_end \
                    and node.generation == generation:
                result_list.append(node.title)
        return result_list

    def get_node_by_title(self, node_title: str) -> Node:
        """
        функция находит в куче по имени и возвращает  узел
        :param node_title:
        :return: Node
        """
        for node in self.all_nodes:
            if node.title == node_title:
                return node

    def get_path_from_start_to_me(self, node_title: str):
        """
        функция определяет путь от старта до указанного имени узла
        (на основе данных в куче, не по связям в БД)
        :param node_title: str
        :return: List[str]
        """
        to_root_str_list = []
        success: bool = False
        cur_node: Node
        cur_node = self.get_node_by_title(node_title)

        while not success:
            to_root_str_list.insert(0, cur_node.title)
            if cur_node.is_start:
                success = True
            else:
                parent_title = cur_node.parent_node_title
                cur_node = self.get_node_by_title(parent_title)
        return to_root_str_list

    def get_valid_child_nodes_by_parent_generation(self, generation: int) -> List[Node]:
        """
        # получить объекты всех ДОЧЕРНИХ валидных узлов из кучи текущего экземпляра маршрута
        (не из БД, а из CurrentRoute->all_nodes)
        от всех узлов с номером генерации, указанной в аргументе
        :param generation: int
        :return: List[Node]
        """
        # получаем список имен всех валидных узлов по номеру генерации из текущей кучи
        parent_list: List[str] = self.get_all_valid_node_titles_by_generation(generation)
        nodes_list: List[Node] = []
        for parent_title in parent_list:
            # по имени каждого элемента создаем объект страницы и поднимаем данные из БД
            parent_page = WikiPage(parent_title)
            parent_page.get_from_db()
            # получаем из БД все дочерние страницы для данной страницы
            for page in get_links_by_parent_page(parent_page):
                # из каждой страницы собираем узел
                node = Node(page.title)
                node.get_from_db()
                node.parent_node_title = parent_title
                node.generation = self.cur_generation
                if node.title == self.finish_page_title:
                    node.is_finish = True
                nodes_list.append(node)
        return nodes_list

    def save_chain_to_db(self):
        for page_tittle in self.cur_path_to_start:
            page = WikiPage(page_tittle)
            page.get_from_db()
            self.add_page_to_chain(page)


class WikiRacer:
    start_time: datetime.datetime
    requests_count: int
    requests_per_minute: int
    links_per_page: int
    max_links_in_route: int
    display_log: bool
    return_route_if_it_exists_in_db: bool

    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.requests_count = 0
        self.requests_per_minute = settings.requests_per_minute
        self.links_per_page = settings.links_per_page
        self.max_links_in_route = settings.max_links_in_route
        self.display_log = settings.display_log
        self.return_route_if_it_exists_in_db = settings.return_route_if_it_exists_in_db

    def print_log_msg(self, msg: str):
        """
        function print message to console, if settings.display_log = true
        :param msg:
        """
        if self.display_log:
            print(msg)

    def find_path(self, start: str, finish: str) -> List[str]:
        """
        main function
        """

        self.print_log_msg(f'START WikiRacer search ({start} -> {finish}) at {self.start_time}')

        # check equality start and finish
        if start == finish:
            raise StartAndFinishEqualityException(start, finish)
        else:
            self.print_log_msg('start_node != finish_node -> OK!')

        # check start page and add to db
        start_node = Node(start)
        self._page_parsing(start_node)
        start_node.get_from_db()
        if start_node.status != PageStatus.PARSED_CAN_BE_USED.value:
            raise StartPageTitleException(start_node.title, start_node.status)
        else:
            start_node.is_start = True
            start_node.generation = 0
            start_node.path_to_start.append(start_node.title)
            self.print_log_msg('start_node -> OK!')

        # check finish page and add to db
        finish_node = Node(finish)
        self._page_parsing(finish_node)
        finish_node.get_from_db()
        if finish_node.status != PageStatus.PARSED_CAN_BE_USED.value:
            raise FinishPageTitleException(finish_node.title, finish_node.status)
        else:
            finish_node.is_finish = True
            self.print_log_msg('finish_node -> OK!')

        # check current route in db, if is exists -> return it
        route = CurrentRoute(start, finish)
        if route.is_exists_in_db() and self.return_route_if_it_exists_in_db:
            route.get_from_db()
            self.print_log_msg(f"The route: {route.get_route_name()} already exists in the database.")
            self.print_log_msg(f'FINISH WikiRacer at {datetime.datetime.now()}')
            return route.get_title_list_from_chain()

        # ============begin search route======================
        route.success = False
        route.cur_node = start_node
        route.cur_generation = 0

        while not route.success:

            # if we have reached the maximum number of generations in the search tree
            if route.cur_generation > self.max_links_in_route:
                raise ExceedingMaxLinksInRouteException()

            # if this is a zero generation (the root of the tree), then
            if route.cur_generation == 0:

                # добавить стартовую страницу в кучу
                route.all_nodes.append(start_node)
                self.print_log_msg(route.get_current_info())

                # делаем шаг в глубь дерева и анализируем потомков
                route.cur_path_to_start = start_node.path_to_start
                route.cur_generation += 1

            # if this is not zero generation, then
            else:
                self.print_log_msg(route.get_current_info())

                # take all valid child nodes (all children) from node(s) with generation -1 (all parents)
                # (page_status = PARSED_CAN_BE_USED, not dead end, generation =-1)
                valid_child_nodes = route.get_valid_child_nodes_by_parent_generation(route.cur_generation - 1)
                child_nodes_for_parsing = []

                # check if the selected list has page with status is_finish
                # if true -> return the list with one element (finish node)
                # if not -> return full list of valid childs
                for node in valid_child_nodes:
                    if node.is_finish and node.title == route.finish_page_title:
                        child_nodes_for_parsing.append(node)
                if not child_nodes_for_parsing:
                    child_nodes_for_parsing = valid_child_nodes

                # iterate list
                for node in child_nodes_for_parsing:
                    # pars the page
                    self._page_parsing(node)
                    node.get_from_db()

                    # if the stack of all previously viewed nodes has current node
                    if node.title in route.get_all_valid_node_titles():
                        # mark this node as dead_end
                        node.is_dead_end = True

                    # add this node to stack
                    route.all_nodes.append(node)

                    # get and save the route from start to me in this node
                    node.path_to_start = route.get_path_from_start_to_me(node.title)

                    # save the chain to current
                    route.cur_path_to_start = node.path_to_start

                    # if the title of current node = the title of finish node
                    if node.title == finish_node.title:
                        node.is_finish = True
                        self.print_log_msg(node.get_current_info())
                        route.success = True
                        # save the route to DB
                        route.add_to_db()
                        # build the chain and save it to DB
                        route.save_chain_to_db()
                        break
                    else:
                        self.print_log_msg(node.get_current_info())

                # go to generation + 1
                route.cur_generation += 1

        else:
            self.print_log_msg(f"Route is founded!!!")
            self.print_log_msg(f'FINISH WikiRacer at {datetime.datetime.now()}')
            return route.get_title_list_from_chain()

    def _request_limiter(self) -> bool:
        """
        The function controls the actual number of requests and the total duration of the program running.
        If the limit on the number of requests per minute (requests_per_minute in the settings) is exceeded,
        the function returns the number of seconds of delay.
        If the limit is not exceeded, then the function returns zero.
        :return: True/False
        """
        total_duration_sec = (datetime.datetime.now() - self.start_time).total_seconds()
        total_duration_min = round(total_duration_sec / 60, 0)
        self.requests_count += 1
        current_req_per_min = round(self.requests_count / total_duration_sec * 60, 1)
        self.print_log_msg(
            f"""Request_limiter: 
duration, min: {total_duration_min}, requests_count: {self.requests_count}, requests_per_min: {current_req_per_min}"""
        )
        if current_req_per_min < self.requests_per_minute:
            return True
        else:
            return False

    def _page_parsing(self, node: Node):
        """
        this function do next operations:
          -if page not in db -> add it
          -if page has no linked pages in db (status == NOT_PARSED)
             -> parsing page
              -if page not in ignore_list_patterns (ignore_list_patterns.py/check_pattern_in_title()):
               -if no more then links_per_page:
                -> add new pages to DB (links from wiki page)
                -> add links 'parent-child' to db (the table 'links')
        :param node: WikiPage:
        """
        # if page not in db -> add it
        node.add_to_db()

        # begin parsing page
        if node.status == PageStatus.NOT_PARSED.value:
            connection_condition = True  # current connection condition
            connection_attempt = 0  # current connection iteration

            response_condition = True  # current response condition
            response_attempt = 0  # current response iteration

            while connection_condition and response_condition:
                if self._request_limiter():
                    try:
                        response = requests.get(node.get_url())
                        response.raise_for_status()  # raise error if not OK
                        # create BeautifulSoup object and pars it
                        page_html = BeautifulSoup(response.text, 'html.parser')
                        mw_content_text_element = page_html.find('div', {'id': 'mw-content-text'})
                        href_list = mw_content_text_element.findAll('a', href=True)

                        count: int = 0
                        for href in href_list:
                            try:
                                title = href['title']
                                if not check_pattern_in_title(title):
                                    if count < self.links_per_page:
                                        node.add_linked_page(title)  # add new page and link to db
                                        count += 1
                            except:
                                continue
                        node.set_page_status(PageStatus.PARSED_CAN_BE_USED.value)
                        break

                    except ConnectionError as conn_exc:
                        if connection_attempt <= settings.connection_retries:
                            self.print_log_msg(f'ConnectionError!!! Attempt:{connection_attempt}.\n')
                            connection_attempt += 1
                            sleep(connection_attempt * settings.connection_delay_if_error)
                        else:
                            connection_condition = False
                            self.print_log_msg(f'ConnectionError!!! Exit!!!\n{conn_exc.args}\n')

                    except HTTPError as http_exc:
                        code = http_exc.response.status_code
                        if code == 404:
                            node.set_page_status(PageStatus.PARSED_NO_SUCH_ARTICLE.value)
                            break

                        if code in [429, 500, 502, 503, 504]:
                            if response_attempt <= settings.response_retries:
                                self.print_log_msg(f'ResponseError!!! Status: {code}. Attempt:{connection_attempt}.\n')
                                response_attempt += 1
                                sleep(response_attempt * settings.response_delay_if_error)
                            else:
                                response_condition = False
                                self.print_log_msg(f'ResponseError!!! Status: {code}. Exit!!!\n')
                else:
                    sleep(1)


# racer = WikiRacer()
# result = racer.find_path('Дружина (військо)', '6 жовтня')
# print(result)
