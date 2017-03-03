import re

from querygraph.exceptions import QueryGraphException
from querygraph.db.connectors import DatabaseConnector
from querygraph.query.template.parameter import TemplateParameter


# =============================================
# Exceptions
# ---------------------------------------------

class QueryTemplateException(QueryGraphException):
    pass


class DependentParameterException(QueryTemplateException):
    pass


class IndependentParameterException(QueryTemplateException):
    pass


# =============================================
# Query Parser Class
# ---------------------------------------------

class QueryTemplate(object):
    """
    Query Template docstring...

    Parameters
    ----------
    query : str
        The query...
    db_connector : DatabaseConnector
        DatabaseConnector instance...

    """

    def __init__(self, query, db_connector):

        self.query = query
        self.query_isolated = True
        if not isinstance(db_connector, DatabaseConnector):
            raise QueryTemplateException("The 'db_connector' arg must be a DatabaseConnector instance.")
        self.db_connector = db_connector

    def render(self, df=None, **independent_param_vals):
        """
        Returns parsed query template string.

        """
        parsed_query = ""
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", self.query)
        for token in tokens:
            # Dependent parameter.
            if token.startswith('{{'):
                tok_expr = token[2:-2].strip()
                # dependent_parameter = QueryParameter(parameter_str=tok_expr)
                dependent_parameter = TemplateParameter(param_str=tok_expr,
                                                        param_type='dependent',
                                                        db_connector=self.db_connector)
                if df is None:
                    raise DependentParameterException("No dataframe was given from which to generate dependent"
                                                      "parameter value(s).")
                parsed_query += dependent_parameter.query_value(df=df)
            # Comment.
            elif token.startswith('{#'):
                pass
            # Independent parameter.
            elif token.startswith('{%'):
                tok_expr = token[2:-2].strip()
                independent_parameter = TemplateParameter(param_str=tok_expr,
                                                          param_type='independent',
                                                          db_connector=self.db_connector)
                if not independent_param_vals:
                    raise IndependentParameterException("Independent parameters present in query and no independent"
                                                        "parameter values given.")
                parsed_query += str(independent_parameter.query_value(independent_params=independent_param_vals))
            else:
                parsed_query += token
        return parsed_query

    def has_dependent_parameters(self):
        """
        Test docstring...


        :return:
        """
        contains_dependent_parameter = False
        tokens = re.split(r"(?s)({{.*?}})", self.query)
        for token in tokens:
            if token.startswith('{{'):
                contains_dependent_parameter = True
                break
        return contains_dependent_parameter

    def execute(self, df=None, **independent_param_vals):
        rendered_query = self.render(df=df, **independent_param_vals)
        df = self.db_connector.execute_query(query=rendered_query)
        return df

    def execute_to_dict(self, df=None, **independent_param_vals):
        pass