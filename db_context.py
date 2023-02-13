"""
this module is an intermediate layer
between the main module (wikiracing.py)
and the postgresql database
"""
from typing import List
from enum import Enum
import datetime
from settings import *
import psycopg2


class DB:
    """
    this class provides a connection, cursor snd commit for database queries,
    and also closes the connection and cursor
    """

    def __init__(self,
                 dbname=POSTGRES_DB,
                 user=POSTGRES_USER,
                 password=POSTGRES_PASSWORD,
                 host=POSTGRES_HOST,
                 port=POSTGRES_PORT):
        self.conn = psycopg2.connect(dbname=dbname,
                                     user=user,
                                     password=password,
                                     host=host,
                                     port=port)
        self.cur = self.conn.cursor()

    def query(self, query):
        self.cur.execute(query)

    def commit(self):
        self.conn.commit()

    def cur_close(self):
        self.cur.close()

    def conn_close(self):
        self.conn.close()

    def close(self):
        self.cur.close()
        self.conn.close()


# ====PAGE_STATUS=======
class PageStatus(Enum):
    """
    this class provides a list of statuses for WikiPage objects
    use like this:
    name = PageStatus(1).name  # gives NOT_SAVED_NOT_PARSED
    value = PageStatus.NOT_SAVED_NOT_PARSED.value  # gives 1
    """

    NOT_PARSED = 1
    PARSED_CAN_BE_USED = 2
    PARSED_NO_SUCH_ARTICLE = 3
    PARSED_THE_ARTICLE_HAS_NO_LINKS = 4


# ====PAGES=======
class WikiPage:
    """
    this class allows you to create wiki page object (table 'pages' in DB)
    and perform basic database operations with objects
    also has methods for operations with related pages (table 'linkes' in DB)
    """

    title: str
    id: int
    created: datetime.datetime
    status: int

    def __init__(self, page_title: str):
        self.title = page_title
        self.id = 0
        self.status = PageStatus.NOT_PARSED.value

    def get_url(self) -> str:
        url = f"{source_link}{self.title.replace(' ', '_')}"
        return url

    def is_exists_in_db(self) -> bool:
        db = DB()
        with db.cur as cursor:
            cursor.execute("SELECT * FROM pages WHERE page_title = %s;", (self.title,))
            count = cursor.rowcount
            db.close()
            if count == 1:
                return True
            else:
                return False

    def get_from_db(self):
        db = DB()
        with db.cur as cursor:
            cursor.execute("SELECT * FROM pages WHERE page_title = %s", (self.title,))
            # if page is exists in db -> get it
            if cursor.rowcount > 0:
                row = cursor.fetchone()
                self.id = row[0]
                self.created = row[2]
                self.status = row[3]
            else:
                self.id = 0
        db.close()

    def add_to_db(self):
        # if not exist in DB
        if not self.is_exists_in_db():
            # save current page
            db = DB()
            with db.cur as cursor:
                sql_string = "INSERT INTO pages (page_title, page_status) VALUES (%s, %s) RETURNING page_id;"
                cursor.execute(sql_string, (self.title, PageStatus.NOT_PARSED.value))
                self.id = cursor.fetchone()[0]
            db.commit()
            db.close()
            self.get_from_db()
        else:
            self.get_from_db()

    def set_page_status(self, new_status: int):
        self.status = new_status
        db = DB()
        with db.cur as cursor:
            sql_string = "UPDATE pages SET page_status = %s WHERE page_id = %s;"
            cursor.execute(sql_string, (self.status, self.id))
        db.commit()
        db.close()

    def has_linked_pages_in_db(self) -> bool:
        db = DB()
        with db.cur as cursor:
            sql_string = "SELECT * FROM links WHERE parent_id = %s;"
            cursor.execute(sql_string, (self.id,))
            count = cursor.rowcount
            db.close()
            if count > 0:
                return True
            else:
                return False

    def add_linked_page(self, linked_page_title: str):
        # create new page
        child_page = WikiPage(linked_page_title)
        child_page.add_to_db()
        # create new link
        if not self.is_exist_linked_page_by_title(linked_page_title):
            db = DB()
            with db.cur as cursor:
                sql_string = "INSERT INTO links (parent_id, child_id) VALUES (%s, %s);"
                cursor.execute(sql_string, (self.id, child_page.id))
            db.commit()
            db.close()

    def add_linked_pages(self, *childs_titles: []):
        for title in childs_titles[0]:
            print(title)
            self.add_linked_page(title)

    def is_exist_linked_page_by_title(self, search_title: str) -> bool:
        db = DB()
        count: int
        with db.cur as cursor:
            sql_str = """
                        SELECT 
                            p2.page_id AS page_id, 
                            p2.page_title AS page_title,
                            p2.created_on AS created_on
                        FROM pages p1
                            LEFT JOIN links l1 ON l1.parent_id = p1.page_id
                            LEFT JOIN pages p2 ON p2.page_id = l1.child_id
                        WHERE p1.page_id = %s AND p2.page_title = %s;
                        """
            cursor.execute(sql_str, (self.id, search_title))
            count = cursor.rowcount
            db.close()
            if count > 0:
                return True
            else:
                return False

    def get_linked_page_by_title(self, search_title: str):
        db = DB()
        with db.cur as cursor:
            sql_str = """
                        SELECT 
                            p2.page_id AS page_id, 
                            p2.page_title AS page_title,
                            p2.created_on AS created_on
                        FROM pages p1
                            LEFT JOIN links l1 ON l1.parent_id = p1.page_id
                            LEFT JOIN pages p2 ON p2.page_id = l1.child_id
                        WHERE p1.page_id = %s AND p2.page_title = %s;
                        """
            cursor.execute(sql_str, (self.id, search_title))
            row = cursor.fetchone()
            linked_page = WikiPage(row[1])
            linked_page.id = row[0]
            linked_page.created = row[2]
        db.close()
        return linked_page


# ====ROUTES=======
class Route:
    """
    this class allows you to create wiki route object (table 'routes' in DB)
    and perform basic database operations with this objects
    also it has methods for operations with chains (table 'route_chains' in DB)
    """
    id: int
    start_page_title: str
    finish_page_title: str
    created: datetime.datetime

    def __init__(self, start: str, finish: str):
        self.start_page_title = start
        self.finish_page_title = finish
        self.id = 0

    def get_route_name(self):
        return f'{self.start_page_title} -> {self.finish_page_title}'

    def is_exists_in_db(self) -> bool:
        db = DB()
        with db.cur as cursor:
            sql_str = "SELECT * FROM routes WHERE start_page_title = %s AND finish_page_title = %s;"
            cursor.execute(sql_str, (self.start_page_title, self.finish_page_title))
            count = cursor.rowcount
            db.close()
            if count > 0:
                return True
            else:
                return False

    def get_from_db(self):
        db = DB()
        with db.cur as cursor:
            sql_str = "SELECT * FROM routes WHERE start_page_title = %s AND finish_page_title = %s;"
            cursor.execute(sql_str, (self.start_page_title, self.finish_page_title))
            # if page is exists in db -> get it
            if cursor.rowcount > 0:
                row = cursor.fetchone()
                self.id = row[0]
                self.created = row[2]
            else:
                self.id = 0
        db.close()

    def add_to_db(self):
        # if not exist in DB
        if not self.is_exists_in_db():
            # save current page
            db = DB()
            with db.cur as cursor:
                sql_string = """INSERT INTO routes (start_page_title, finish_page_title) 
                                VALUES (%s, %s) RETURNING route_id;"""
                cursor.execute(sql_string, (self.start_page_title, self.finish_page_title))
                self.id = cursor.fetchone()[0]
            db.commit()
            db.close()
            self.get_from_db()
        else:
            self.get_from_db()

    def count_pages_in_chain(self) -> int:
        if self.id == 0:
            return 0
        else:
            count: int = 0
            db = DB()
            with db.cur as cursor:
                sql_string = "SELECT chain_id FROM route_chains WHERE route_id = %s ORDER BY page_order;"
                cursor.execute(sql_string, (self.id,))
                count = cursor.rowcount
                db.close()
                return count

    def is_exists_pages_in_chain_in_route(self, page: WikiPage) -> bool:
        if self.id == 0:
            return 0
        else:
            count: int = 0
            db = DB()
            with db.cur as cursor:
                sql_string = """SELECT chain_id 
                                FROM route_chains 
                                WHERE route_id = %s AND page_id = %s;"""
                cursor.execute(sql_string, (self.id, page.id))
                count = cursor.rowcount
                db.close()
            if count == 0:
                return False
            else:
                return True

    def add_page_to_chain(self, page: WikiPage):
        if not self.is_exists_pages_in_chain_in_route(page):
            db = DB()
            with db.cur as cursor:
                sql_string = "INSERT INTO route_chains (route_id, page_id, page_order) VALUES (%s, %s, %s);"
                next_order_number_in_chain = self.count_pages_in_chain() + 1
                cursor.execute(sql_string, (self.id, page.id, next_order_number_in_chain))
            db.commit()
            db.close()

    def get_page_list_from_chain(self) -> List[WikiPage]:
        if self.id == 0:
            return []
        else:
            pages_list = []
            db = DB()
            with db.cur as cursor:
                sql_string = """
                                SELECT rc.page_id AS page_id, p.page_title AS page_title
                                FROM route_chains rc
                                    INNER JOIN pages p ON p.page_id = rc.page_id
                                WHERE rc.route_id = %s 
                                ORDER BY rc.page_order;
                """
                cursor.execute(sql_string, (self.id,))
                if cursor.rowcount > 0:
                    for row in cursor:
                        page = WikiPage(row[1])
                        page.get_from_db()
                        pages_list.append(page)
            db.close()
        return pages_list

    def get_title_list_from_chain(self) -> List[str]:
        page_list = self.get_page_list_from_chain()
        title_list = []
        for page in page_list:
            title_list.append(page.title)
        return title_list


# ======STATIC METHODS========
def get_links_by_parent_page(parent_page: WikiPage) -> List[WikiPage]:
    result_list = []
    db = DB()
    with db.cur as cursor:
        sql_str = """
                    SELECT 
                        p2.page_id as page_id, 
                        p2.page_title as page_title,
                        p2.created_on as created_on
                    FROM pages p1
                        LEFT JOIN links l1 ON l1.parent_id = p1.page_id
                        LEFT JOIN pages p2 ON p2.page_id = l1.child_id
                    WHERE p1.page_id = %s
                    ORDER BY p2.page_title;
                  """
        cursor.execute(sql_str, (parent_page.id,))
        if cursor.rowcount > 0:
            for row in cursor:
                linked_page = WikiPage(row[1])
                linked_page.id = row[0]
                linked_page.created = row[2]
                result_list.append(linked_page)
    db.close()
    return result_list


def get_pages_all() -> List[WikiPage]:
    page_list = []
    db = DB()
    with db.cur as cursor:
        sql_str = "SELECT * FROM pages;"
        cursor.execute(sql_str)
        if cursor.rowcount > 0:
            for row in cursor:
                page = WikiPage(row[1])
                page.id = row[0]
                page.created = row[2]
                page_list.append(page)
    db.close()
    return page_list


def clear_all_chains():
    db = DB()
    with db.cur as cursor:
        sql_str = "DELETE FROM route_chains;"
        cursor.execute(sql_str)
    db.commit()
    db.close()


def clear_all_routes():
    db = DB()
    with db.cur as cursor:
        sql_str = "DELETE FROM routes;"
        cursor.execute(sql_str)
    db.commit()
    db.close()


def clear_all_links():
    db = DB()
    with db.cur as cursor:
        sql_str = "DELETE FROM links;"
        cursor.execute(sql_str)
    db.commit()
    db.close()


def clear_all_pages():
    db = DB()
    with db.cur as cursor:
        sql_str = "DELETE FROM pages;"
        cursor.execute(sql_str)
    db.commit()
    db.close()


def clear_all_tables():
    clear_all_chains()
    clear_all_routes()
    clear_all_links()
    clear_all_pages()


# clear_all_tables()
