def compare_dictionaries(dict_1, dict_2, dict_1_name="first", dict_2_name="second", path=""):
    """Compare two dictionaries recursively to find non mathcing elements

    Args:
        dict_1: dictionary 1
        dict_2: dictionary 2

    Returns:

    """
    err = ''
    key_err = ''
    value_err = ''
    old_path = path
    equals = True
    for k in dict_1.keys():
        path = old_path + "[{}]".format(k)
        if not k in dict_2:
            key_err += "Key %s%s not in %s\n" % (dict_1_name, path, dict_2_name)
            equals = False
        else:
            if isinstance(dict_1[k], dict) and isinstance(dict_2[k], dict):
                result, string = compare_dictionaries(dict_1[k], dict_2[k], dict_1_name, dict_2_name, path)
                err += string
                if not result:
                    equals = result
            else:
                if dict_1[k].__class__.__name__ == "LinkCapacityZero" and dict_1[
                    k].__class__ == dict_2[k].__class__:
                    continue
                if dict_1[k] != dict_2[k]:
                    equals = False
                    value_err += "Value of %s%s \n(%s) \nnot same as %s%s \n(%s)\n" \
                                 % (dict_1_name, path, dict_1[k], dict_2_name, path, dict_2[k])

    for k in dict_2.keys():
        path = old_path + "[{}]".format(k)
        if not k in dict_1:
            equals = False
            key_err += "Key %s%s not in %s\n" % (dict_2_name, path, dict_1_name)
    return equals, key_err + value_err + err
