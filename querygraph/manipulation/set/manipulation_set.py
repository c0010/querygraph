from abc import ABCMeta, abstractmethod
from collections import defaultdict

import pandas as pd
import pyparsing as pp

from querygraph.exceptions import QueryGraphException
from querygraph.manipulation.expression.evaluator import Evaluator
from querygraph.manipulation import common_parsers
from querygraph.utils.abstract_cls_method import abstractclassmethod


# =============================================
# Manipulation Exceptions
# ---------------------------------------------

class ManipulationException(QueryGraphException):
    pass


class ManipulationSetException(QueryGraphException):
    pass


class ConfigurationException(ManipulationException):
    pass


# =============================================
# Manipulation Abstract Base Class
# ---------------------------------------------

class Manipulation(object):

    __metaclass__ = ABCMeta

    def __call__(self, df, evaluator=None):
        return self.execute(df, evaluator)

    def execute(self, df, evaluator=None):
        return self._execute(df, evaluator)

    @abstractmethod
    def _execute(self, df, evaluator=None):
        pass

    @abstractclassmethod
    def parser(cls):
        pass


# =============================================
# Manipulation Types
# ---------------------------------------------

class Mutate(Manipulation):

    def __init__(self, mutations):
        self.mutations = mutations

    def _execute(self, df, evaluator=None):
        if not isinstance(evaluator, Evaluator):
            raise ManipulationException

        for mutation in self.mutations:
            expr_evaluator = Evaluator(df=df)
            df[mutation['col_name']] = expr_evaluator.eval(expr_str=mutation['col_expr'])
        return df

    @classmethod
    def parser(cls):
        lpar = pp.Suppress("(")
        rpar = pp.Suppress(")")
        mutate = pp.Suppress('mutate')
        col_name = pp.Word(pp.alphas, pp.alphanums + "_$")

        expr_evaluator = Evaluator(deferred_eval=True)
        col_expr = expr_evaluator.parser()

        mutation = col_name + pp.Suppress("=") + col_expr
        mutation.setParseAction(lambda x: {'col_name': x[0], 'col_expr': x[1]})
        mutations = pp.Group(pp.delimitedList(mutation))
        parser = mutate + lpar + mutations + rpar
        parser.setParseAction(lambda x: Mutate(mutations=x))
        return parser


class Rename(Manipulation):

    def __init__(self, columns):
        self.columns = columns

    def _execute(self, df, evaluator=None):
        df = df.rename(columns=self.columns)
        return df

    @classmethod
    def parser(cls):
        rename = pp.Suppress("rename")
        rename_kwarg = common_parsers.column + pp.Suppress("=") + common_parsers.column
        rename_kwarg.setParseAction(lambda x: {x[0]: x[1]})

        kwargs = pp.Group(pp.delimitedList(rename_kwarg))
        kwargs.setParseAction(lambda x: {k: v for d in x for k, v in d.items()})

        parser = rename + pp.Suppress("(") + kwargs + pp.Suppress(")")
        parser.setParseAction(lambda x: Rename(columns=x[0]))
        return parser


class Select(Manipulation):

    def __init__(self, columns):
        self.columns = columns

    def _execute(self, df, evaluator=None):
        existing_columns = list(df.columns.values)
        unneeded_cols = list(set(existing_columns) - set(self.columns))
        return df.drop(unneeded_cols, inplace=False, axis=1)

    @classmethod
    def parser(cls):
        select = pp.Suppress("select")
        column = common_parsers.column
        parser = select + pp.Suppress("(") + pp.Group(pp.delimitedList(column)) + pp.Suppress(")")
        parser.setParseAction(lambda x: Select(columns=x[0]))
        return parser


class Remove(Manipulation):

    def __init__(self, columns):
        self.columns = columns

    def _execute(self, df, evaluator=None):
        return df.drop(self.columns, inplace=False, axis=1)

    @classmethod
    def parser(cls):
        remove = pp.Suppress("remove")
        column = common_parsers.column
        parser = remove + pp.Suppress("(") + pp.Group(pp.delimitedList(column)) + pp.Suppress(")")
        parser.setParseAction(lambda x: Remove(columns=x[0]))
        return parser


class Flatten(Manipulation):

    def __init__(self, column):
        self.column = column

    def _execute(self, df, evaluator=None):
        col_flat = pd.DataFrame([[i, x]
                                 for i, y in df[self.column].apply(list).iteritems()
                                 for x in y], columns=['I', self.column])
        col_flat = col_flat.set_index('I')
        df = df.drop(self.column, 1)
        df = df.merge(col_flat, left_index=True, right_index=True)
        df = df.reset_index(drop=True)
        return df

    @classmethod
    def parser(cls):
        unpack = pp.Suppress("flatten")
        column = common_parsers.column
        parser = unpack + pp.Suppress("(") + column + pp.Suppress(")")
        parser.setParseAction(lambda x: Flatten(column=x[0]))
        return parser


class Unpack(Manipulation):

    def __init__(self, unpack_list):
        self.unpack_list = unpack_list

    @staticmethod
    def unpack_dict(row_dict, key_list):
        return reduce(dict.__getitem__, key_list, row_dict)

    def _execute(self, df, evaluator=None):
        for unpack_dict in self.unpack_list:
            packed_col = unpack_dict['packed_col']
            key_list = unpack_dict['key_list']
            new_col_name = unpack_dict['new_col_name']
            df[new_col_name] = df[packed_col].apply(lambda x: self.unpack_dict(row_dict=x, key_list=key_list))
        return df

    @classmethod
    def parser(cls):
        unpack = pp.Suppress("unpack")

        packed_col_name = common_parsers.column
        dict_key = pp.Suppress("[") + pp.QuotedString(quoteChar="'") + pp.Suppress("]")
        dict_key_grp = pp.Group(pp.OneOrMore(dict_key))
        new_col_name = common_parsers.column

        unpack_arg = new_col_name + pp.Suppress("=") + packed_col_name + dict_key_grp
        unpack_arg.setParseAction(lambda x: {'packed_col': x[1], 'key_list': x[2], 'new_col_name': x[0]})

        parser = unpack + pp.Suppress("(") + pp.delimitedList(unpack_arg) + pp.Suppress(")")
        parser.setParseAction(lambda x: Unpack(unpack_list=x))
        return parser


class GroupedSummary(Manipulation):

    lambda_summaries = {'spread': lambda x: max(x) - min(x)}

    def __init__(self, group_by, aggregations):
        self.group_by = group_by
        self.aggregations = aggregations
        self._aggregations = defaultdict(dict)
        self._merge_aggregations()

    def _merge_aggregations(self):
        for agg_dict in self.aggregations:
            summary_type = agg_dict['summary_type']
            if summary_type in self.lambda_summaries:
                self._aggregations[agg_dict['target_col']][agg_dict['summary_col_name']] = self.lambda_summaries[summary_type]
            else:
                self._aggregations[agg_dict['target_col']][agg_dict['summary_col_name']] = agg_dict['summary_type']

    @classmethod
    def parser(cls):
        group_by = pp.Suppress("group_by")
        column = common_parsers.column
        group_by_block = group_by + pp.Suppress("(") + pp.Group(pp.delimitedList(column)) + pp.Suppress(")")

        summarize = pp.Suppress("summarize")
        summary_col_name = common_parsers.column
        summary_type = pp.Word(pp.alphas, pp.alphanums + "_$")
        target_column = common_parsers.column
        single_summary = summary_col_name + pp.Suppress("=") + summary_type +\
                         pp.Suppress("(") + target_column + pp.Suppress(")")
        single_summary.setParseAction(lambda x: {'summary_col_name': x[0], 'summary_type': x[1], 'target_col': x[2]})
        summarize_block = summarize + pp.Suppress("(") + pp.Group(pp.delimitedList(single_summary)) + pp.Suppress(")")

        parser = group_by_block + pp.Suppress(">>") + summarize_block
        parser.setParseAction(lambda x: GroupedSummary(group_by=x[0], aggregations=x[1]))
        return parser

    def _execute(self, df, evaluator=None):
        return df.groupby(self.group_by).agg(self._aggregations)


class DropNa(Manipulation):

    def _execute(self, df, evaluator=None):
        return df.dropna()

    @classmethod
    def parser(cls):
        drop_na = pp.Suppress("group_by")
        parser = drop_na + pp.Suppress("()")
        parser.setParseAction(lambda x: DropNa())
        return parser


# =============================================
# Manipulation Set
# ---------------------------------------------


class ManipulationSet(object):

    def __init__(self):
        self.manipulations = list()

    def __contains__(self, manipulation_type):
        return any(isinstance(x, manipulation_type) for x in self.manipulations)

    def __add__(self, other):
        if not isinstance(other, Manipulation):
            raise ConfigurationException("Only Manipulation instances can be added to ManipulationSet.")
        else:
            self.manipulations.append(other)
        return self

    __radd__ = __add__

    def __iter__(self):
        for x in self.manipulations:
            yield x

    def __lshift__(self, other):
        parser = self.parser()
        manipulations = parser.parseString(other)
        for manipulation in manipulations:
            self.manipulations.append(manipulation)
        return self

    def __nonzero__(self):
        if len(self.manipulations) > 0:
            return True
        else:
            return False

    def execute(self, df):
        evaluator = Evaluator()
        for manipulation in self:
            df = manipulation.execute(df, evaluator)
        return df

    def parser(self):
        manipulation = (Unpack.parser() | Mutate.parser() | Flatten.parser() |
                        Select.parser() | Remove.parser() | GroupedSummary.parser() |
                        DropNa.parser())
        manipulation_set = pp.delimitedList(manipulation, delim='>>')
        return manipulation_set

    def append_from_str(self, set_str):
        parser = self.parser()
        manipulations = parser.parseString(set_str)
        for manipulation in manipulations:
            self.manipulations.append(manipulation)
        return self


