import unittest

from wikiracing import (WikiRacer,
                        StartAndFinishEqualityException,
                        StartPageTitleException,
                        FinishPageTitleException,
                        ExceedingMaxLinksInRouteException)


class WikiRacerTest(unittest.TestCase):

    racer = WikiRacer()

    # =======POSITIVE TESTS==========
    # group of tests with an expected positive result,
    # where param 'return_route_if_it_exists_in_db' = True
    # with this setting, the function immediately returns the previously saved route (without searching)

    def test_1_1(self):
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = True
        path = self.racer.find_path('Дружба', 'Рим')
        self.assertEqual(path, ['Дружба', 'Якопо Понтормо', 'Рим'])

    def test_1_2(self):
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = True
        path = self.racer.find_path('Мітохондріальна ДНК', 'Вітамін K')
        self.assertEqual(path, ['Мітохондріальна ДНК', 'ND4', 'Убіхінон', 'Вітамін K'])

    def test_1_3(self):
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = True
        path = self.racer.find_path('Марка (грошова одиниця)', 'Китайський календар')
        self.assertEqual(path, ['Марка (грошова одиниця)', '1549', 'Китайський календар'])

    def test_1_4(self):
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = True
        path = self.racer.find_path('Фестиваль', 'Пілястра')
        self.assertEqual(path, ['Фестиваль', 'Бароко', 'Пілястра'])

    def test_1_5(self):
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = True
        path = self.racer.find_path('Дружина (військо)', '6 жовтня')
        self.assertEqual(path, ['Дружина (військо)', 'Wayback Machine', '24 жовтня', '6 жовтня'])

    # test with an expected positive result,
    # where param 'return_route_if_it_exists_in_db' = False
    # and param 'max_links_in_route' is more than needed to get the page you're looking for (by default in settings = 4)
    # with this setting, the function will search finish page in the database
    # or on the website if the database does not have these links

    def test_2_1(self):
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = False
        path = self.racer.find_path('Дружба', 'Рим')
        self.assertEqual(path, ['Дружба', 'Якопо Понтормо', 'Рим'])

    # def test_2_2(self):
    #     self.racer.display_log = False
    #     self.racer.return_route_if_it_exists_in_db = False
    #     path = self.racer.find_path('Мітохондріальна ДНК', 'Вітамін K')
    #     self.assertEqual(path, ['Мітохондріальна ДНК', 'ND4', 'Убіхінон', 'Вітамін K'])
    #
    # def test_2_3(self):
    #     self.racer.display_log = False
    #     self.racer.return_route_if_it_exists_in_db = False
    #     path = self.racer.find_path('Марка (грошова одиниця)', 'Китайський календар')
    #     self.assertEqual(path, ['Марка (грошова одиниця)', '1549', 'Китайський календар'])
    #
    # def test_2_4(self):
    #     self.racer.display_log = False
    #     self.racer.return_route_if_it_exists_in_db = False
    #     path = self.racer.find_path('Фестиваль', 'Пілястра')
    #     self.assertEqual(path, ['Фестиваль', 'Бароко', 'Пілястра'])
    #
    # def test_2_5(self):
    #     self.racer.display_log = False
    #     self.racer.return_route_if_it_exists_in_db = False
    #     path = self.racer.find_path('Дружина (військо)', '6 жовтня')
    #     self.assertEqual(path, ['Дружина (військо)', 'Азовське козацьке військо', '23 жовтня', '6 жовтня'])

    # =======NEGATIVE TESTS==========
    # check if Start page is wrong (there is no such page with this name on the site)
    def test_start_and_finish_equality(self):
        start = 'Дружба'
        finish = 'Дружба'
        self.racer.display_log = False
        expected_exception = f"Start page {start} and Finish page {finish} cannot have the same name!"
        with self.assertRaises(StartAndFinishEqualityException) as e:
            self.racer.find_path(start, finish)
        self.assertEqual(expected_exception, e.exception.args[0])

    # check if Start page is wrong (there is no such page with this name on the site)
    # this test also checks the functionality of the parser
    def test_start_page_is_wrong(self):
        start = 'Дружб'  # is wrong
        finish = 'Рим'
        page_status = 'PARSED_NO_SUCH_ARTICLE'
        self.racer.display_log = False
        expected_exception = f"Start page: {start} has problems! ParsCode: {page_status}."
        with self.assertRaises(StartPageTitleException) as e:
            self.racer.find_path(start, finish)
        self.assertEqual(expected_exception, e.exception.args[0])

    # check if Finish page is wrong (there is no such page with this name on the site)
    # this test also checks the functionality of the parser
    def test_finish_page_is_wrong(self):
        start = 'Дружба'
        finish = 'Римм'  # is wrong
        page_status = 'PARSED_NO_SUCH_ARTICLE'
        self.racer.display_log = False
        expected_exception = f"Finish page: {finish} has problems! ParsCode: {page_status}."
        with self.assertRaises(FinishPageTitleException) as e:
            self.racer.find_path(start, finish)
        self.assertEqual(expected_exception, e.exception.args[0])

    # check if the Route is not founded and the maximum number of links in a route is exceeded
    # this test with an expected negative result, where param 'return_route_if_it_exists_in_db' = False
    # and param 'max_links_in_route' less than needed to get the page you're looking for (need - 4, set - 1)
    # with this setting, the function will search finish page in the database
    # or on the website if the database does not have these links
    def test_exceeding_max_links_in_route(self):
        start = 'Мітохондріальна ДНК'
        finish = 'Вітамін K'
        self.racer.display_log = False
        self.racer.return_route_if_it_exists_in_db = False
        self.racer.max_links_in_route = 1
        expected_exception = "The maximum number of hops in a route has been reached and no finish page has been found!"
        with self.assertRaises(ExceedingMaxLinksInRouteException) as e:
            self.racer.find_path(start, finish)
        self.assertEqual(expected_exception, e.exception.args[0])


if __name__ == '__main__':
    unittest.main()
