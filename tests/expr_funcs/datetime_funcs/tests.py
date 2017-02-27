import unittest
import datetime


from querygraph.evaluation import expr_funcs
from querygraph.evaluation.expr_funcs import ExprFuncException


to_str = expr_funcs.DateTimeToString()


class ToStringTests(unittest.TestCase):

    def test_datetime_execute(self):
        test_dt = datetime.datetime(2009, 1, 6, 1, 1, 1)
        expected_value = '2009-01-06 01:01:01'
        self.assertEquals(expected_value, to_str(test_dt, format='%Y-%m-%d %H:%M:%S'))

    def test_bad_type_execute(self):
        self.assertRaises( ExprFuncException, to_str, target='funzone', format='%Y-%m-%d %H:%M:%S')