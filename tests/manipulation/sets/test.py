import unittest
import datetime

import pandas as pd

from querygraph.manipulation.set import ManipulationSet, Mutate, Rename


test_df = pd.DataFrame({'A': [1, 2, 3, 4],
                        'B': [0, 0, 0, 0],
                        'C': ['a', 'b', 'c', 'd'],
                        'D': ['A', 'B', 'C', 'D'],
                        'E': ['Abc', 'Abc', 'Abc', 'Abc'],
                        'F': ['abc', 'abc', 'abc', 'abc'],
                        'G': ['ABC', 'ABC', 'ABC', 'ABC'],
                        'H': [datetime.datetime(2009, 1, 6, 1, 1, 1) for i in range(0, 4)],
                        'I': ['2009-01-06 01:01:01' for j in range(0, 4)],
                        'J': ['2009-01-06' for k in range(0, 4)]})


def series_equal(a, b):
    return a.equals(b)


class ExecutionTests(unittest.TestCase):

    def test_mutate(self):
        manipulation_set = ManipulationSet()
        manipulation_set += Mutate(col_name='test_col', col_expr='A + B')
        result_df = manipulation_set.execute(df=test_df)
        self.assertTrue(series_equal(result_df['test_col'], test_df['A']))

    def test_rename(self):
        manipulation_set = ManipulationSet()
        manipulation_set += Rename(old_column_name='A', new_column_name='new_col')
        result_df = manipulation_set.execute(df=test_df)
        self.assertTrue('new_col' in result_df)


def main():
    unittest.main()

if __name__ == '__main__':
    main()