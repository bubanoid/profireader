from functools import wraps
from flask import jsonify, request, g, abort
from functools import reduce
from sqlalchemy.orm import relationship, backref, make_transient, class_mapper
import datetime
from time import sleep


def ok(func):
    @wraps(func)
    def function_json(*args, **kwargs):
        # try:
        sleep(0.5)
        if 'json' in kwargs:
            del kwargs['json']
        ret = func(request.json, *args, **kwargs)
        return jsonify({'data': ret, 'ok': True, 'error_code': 'ERROR_NO_ERROR'})
        # except Exception as e:
        #     return jsonify({'ok': False, 'error_code': -1, 'result': str(e)})

    return function_json


def replace_brackets(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs:
            for ch in ['{', '}', ' ']:
                for key in kwargs:
                    if ch in kwargs[key]:
                        kwargs[key] = kwargs[key].replace(ch, "")
        return func(*args, **kwargs)

    return wrapper


def from_request():
    from flask import current_app
    res = {}
    if current_app:
        with current_app.app_context():
            res = request.view_args
    return res


# make check for user groups!!!
def can_global(*rights_lambda_rule, **kwargs):
    rez = reduce(
        lambda x, y:
        x or y[list(y.keys())[0]](list(y.keys()), **kwargs),
        rights_lambda_rule, False)
    return rez

# if there is need to use check rights inside the controller (view function)
# you can do it in the following way:
#
# rights_lambda_rule = simple_permissions(frozenset('edit'))
# if not can_global(rights_lambda_rule,
#                   user=current_user,
#                   company_id=company_id):
#     abort(403)


def check_rights(*rights_lambda_rule):
    # (rights, lambda_func) = rights_lambda_rule.items()[0]
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not can_global(*rights_lambda_rule, **kwargs):
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def convert_col_to_arrays(*args):
    pass


def need_we_column(name, arr, is_relationship=False):
    realname = name if name in arr else '*'
    if not is_relationship:
        if realname in arr:
            if len(arr[realname]) > 0:
                raise ValueError("you ask for sub-attribute of Column instance `%s` (not Relationship)" % (realname,))
            return True
        else:
            return False
    else:
        if realname in arr:
            if len(arr[name]) == 0:
                raise ValueError(
                    "You ask for Relationship `%s` instance, but don't ask for any sun-attribute in it" % (realname,))
            return arr[name]
        else:
            return False


def object_to_dict(obj, *args, prefix=''):
    ret = {}

    req_columns = {}
    req_relationships = {}
    for argument in args:
        columnsdevided = argument.split('.')
        if len(columnsdevided) == 1:
            req_columns[argument] = True
        else:
            req_relationname = columnsdevided.pop(0)
            if req_relationname not in req_relationships:
                req_relationships[req_relationname] = []
            req_relationships[req_relationname].append('.'.join(columnsdevided))

    # req_columns = list(set(req_columns))
    # req_relationships = {relationname:convert_col_to_arrays(*nextlevelcols) for relationname,nextlevelcols in relationships}

    columns = class_mapper(obj.__class__).columns
    realations = {a:b for (a,b) in  class_mapper(obj.__class__).relationships.items()}

    get_key_value = lambda o: o.isoformat() if isinstance(o, datetime.datetime) else o
    for col in columns:
        if col.key in req_columns or '*' in req_columns:
            ret[col.key] = get_key_value(getattr(obj, col.key))
            if col.key in req_columns:
                del req_columns[col.key]
    if '*' in req_columns:
        del req_columns['*']

    if len(req_columns) > 0:
        columns_not_in_relations = list(set(req_columns.keys()) - set(realations.keys()))
        if len(columns_not_in_relations) > 0:
            raise ValueError(
                "you requested not existing attribute(s) `%s%s`" % (prefix, '`, `'.join(columns_not_in_relations),))
        else:
            raise ValueError("you requested for attribute(s) but relationships found `%s%s`" % (
            prefix, '`, `'.join(set(realations.keys()).intersection(req_columns.keys())),))

    for relationname, relation in realations.items():
        if relationname in req_relationships or '*' in req_relationships:
            if relationname in req_relationships:
                nextlevelargs = req_relationships[relationname]
                del req_relationships[relationname]
            else:
                nextlevelargs = req_relationships['*']
            related_obj = getattr(obj, relationname)
            if relation.uselist:
                ret[relationname] = [object_to_dict(child, *nextlevelargs, prefix = prefix + relationname + '.') for child in
                                     related_obj]
            else:
                ret[relationname] = object_to_dict(related_obj, *nextlevelargs, prefix = prefix + relationname + '.')

    if '*' in req_relationships:
        del req_relationships['*']

    if len(req_relationships) > 0:
        relations_not_in_columns = list(set(req_relationships.keys()) - set(columns))
        if len(relations_not_in_columns) > 0:
            raise ValueError(
                "you requested not existing relation(s) `%s%s`" % (prefix, '`, `'.join(relations_not_in_columns),))
        else:
            raise ValueError("you requested for relation(s) but column(s) found `%s%s`" % (
            prefix, '`, `'.join(set(columns).intersection(req_relationships)),))

    return ret



    # for column in
    # for name, relation in class_mapper(obj.__class__).relationships.items():
    #     if name in show or show == '*':
    #         related_obj = getattr(obj, name)
    #         if show == '*':
    #             innextlevel = ['id']
    #         else:
    #             innextlevel = ['id'] if show[name] == True else show[name]
    #         if relation.uselist:
    #             ret[name] = [object_to_dict(child, innextlevel) for child in related_obj]
    #         else:
    #             ret[name] = object_to_dict(related_obj, innextlevel)
    #
    #
    # columns = class_mapper(obj.__class__).columns
    # get_key_value = lambda c: (c, getattr(obj, c).isoformat()) if isinstance(getattr(obj, c), datetime.datetime) else (c, getattr(obj, c))
    # ret = dict([get_key_value(col.key) for col in columns if col.key in show or show == '*'])
    #
    # for name, relation in class_mapper(obj.__class__).relationships.items():
    #     if name in show or show == '*':
    #         related_obj = getattr(obj, name)
    #         if show == '*':
    #             innextlevel = ['id']
    #         else:
    #             innextlevel = ['id'] if show[name] == True else show[name]
    #         if relation.uselist:
    #             ret[name] = [object_to_dict(child, innextlevel) for child in related_obj]
    #         else:
    #             ret[name] = object_to_dict(related_obj, innextlevel)




    #
    #
    # ret = {}
    # if isinstance(fields, dict):
    #     for fieldname in fields:
    #         atr = getattr(obj, fieldname)
    #         if isinstance(atr, list):
    #             ret[fieldname] = [object_to_dict(i, fields[fieldname]) for i in atr]
    #         elif isinstance(atr, Base):
    #             ret[fieldname] = object_to_dict(atr, fields[fieldname])
    #         else:
    #             ret[fieldname] = atr
    #

# mapper = class_mapper(obj.__class__)
# columns = [column.key for column in mapper.columns]
# get_key_value = lambda c: (c, getattr(obj, c).isoformat()) if isinstance(getattr(obj, c), datetime.datetime) else (c, getattr(obj, c))
# out = dict(map(get_key_value, columns))
# for name, relation in mapper.relationships.items():
#     related_obj = getattr(obj, name)
#     if relation not in found or relation.uselist:
#         found.add(relation)
#         print((obj, name, relation, relation.uselist))
#         if related_obj is not None:
#             if relation.uselist:
#                 out[name] = [object_to_dict(child, found) for child in related_obj]
#             else:
#                 out[name] = object_to_dict(related_obj, found)
#     # else:
#     #     if relation.uselist:
#     #         out[name] = [object_to_dict(child, found) for child in related_obj]
#     #     else:
#     #         out[name] = object_to_dict(related_obj, found)
#
# return out
