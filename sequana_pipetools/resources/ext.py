""" Script used by pykwalify to validate config file.
The nullable option is derived to control if an optional rule has some empty keys.
"""
from pykwalify.errors import SchemaError


STRING_TYPE = {"text", "str"}


def check_optionnal(value, rule_obj):
    for key, rule in rule_obj.mapping.items():
        if rule.type in STRING_TYPE and rule.required and not rule.nullable:
            try:
                yield key, len(value[key]) > 0
            except TypeError:
                yield key, False
        else:
            yield key, True


def ext_map_optionnal(value, rule_obj, path):
    todo = value.get("do")
    if todo:
        for key, value_check in check_optionnal(value, rule_obj):
            if not value_check:
                raise SchemaError(f"Mandatory value is missing at {path}/{key}")
    return True
