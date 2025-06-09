from django.test import TestCase
from base.classes.util.env_helper import EnvHelper


session = EnvHelper()


class SessionHelperTestCase(TestCase):
    def setUp(self):
        pass

    def test_fake_session(self):
        """
        Since the session does not exist while unit testing, a dict is used in its place.
        This tests that the dict is functioning as expected
        """
        fake_session = session.session
        self.assertTrue(type(fake_session) is dict, "Session should be a dict")

        test_var_1 = "unit_test_value"
        test_val_1 = "This is a unit test..."
        session.set_session_variable(test_var_1, test_val_1)
        self.assertTrue(
            session.get_session_variable(test_var_1) == test_val_1,
            "Session var not set or retrieved",
        )

        test_var_2 = "unit_test_temp_value"
        test_val_2 = "This is another unit test..."
        session.set_page_scope(test_var_2, test_val_2)
        self.assertTrue(
            session.get_page_scope(test_var_2) == test_val_2,
            "Page scope var not set or retrieved",
        )
        session.clear_page_scope()
        self.assertTrue(
            session.get_page_scope(test_var_2) is None, "Page scope not cleared"
        )
        self.assertTrue(
            session.get_session_variable(test_var_1) == test_val_1,
            "Regular session mistakenly cleared",
        )

    def test_cache_keys(self):
        key = session.test_cache_key()
        self.assertTrue(type(key) is str)
        self.assertTrue("test_cache_keys" in key)

    def test_store_recall_string(self):
        value = "fdfsdfd78fsd"
        session.test_store_recall(value)
        self.assertTrue(session.test_store_recall() == value)

    def test_store_recall_dict(self):
        value = {"one": "test", "two": 4, "three": [1, 2, 3, 4]}
        session.test_store_recall(value)
        response = session.test_store_recall()
        self.assertTrue(type(response) is dict)
        self.assertTrue(len(response) == 3)
        self.assertTrue(len(response["three"]) == 4)

        # Changing the original (mutable) response will affect the cached value as well
        value["four"] = "testing"
        self.assertTrue(len(response) == 4)
        self.assertTrue(response["four"] == "testing")
        self.assertTrue(response == value)
