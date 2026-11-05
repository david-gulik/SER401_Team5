#!/usr/bin/env python3
"""
Shoggoth - A Gradescope compatible tool for performing automatic assessment of Java homework, using static and
dynamic analysis.
"""
__author__ = "Ruben Acuna"

import os
import shutil
import javalang
import json

import analysis_java_perf
import analysis_java_checkstyle
import gradescope_result


def extract_imports(filename, cu):
    import_packages = [(p.path, p.wildcard) for p in cu.imports]

    return import_packages


# extract type references
def extract_referenced_types(cu):
    type_literals = set()

    type_references = []
    for path, node_class in cu.filter(javalang.tree.ReferenceType):
        already_discovered = False

        for known_reference in type_references:
            other = known_reference
            while other:
                if node_class == other:
                    already_discovered = True
                other = other.sub_type

        if not already_discovered:
            type_references.extend([node_class])

    for ref_type in type_references:
        parts = []

        while ref_type:
            parts += [ref_type.name]
            ref_type = ref_type.sub_type

        literal = ".".join(parts)
        type_literals.add(tuple([literal, False]))

    return type_literals


def find_disallowed_packages(filepaths, whitelist):
    imported_packages = set()
    referenced_types = set()

    # find all packages in use or referenced
    for filename in filepaths:
        if os.path.isfile(filename):
            with open(filename, "r") as file:
                data = file.read()
                cu = javalang.parse.parse(data)

                imported_packages.update(extract_imports(filename, cu))
                referenced_types.update(extract_referenced_types(cu))

    # whitelisting imports
    all = imported_packages

    referenced_types = set([x for x in referenced_types if "java." in x[0]])  # less its stdlib, skip it
    all.update(referenced_types)

    disallowed = [p for p in all if p[0] not in whitelist or p[1]]

    return disallowed


def body_has_repetition(class_name, method_name, body):
    if not body:
        return False
    elif type(body) is list:
        for statement in body:
            if statement_has_repetition(class_name, method_name, statement):
                return True
        return False
    else:
        return statement_has_repetition(class_name, method_name, body)


def statement_has_repetition(class_name, method_name, statement):
    # see https://github.com/c2nes/javalang/blob/master/javalang/tree.py

    if type(statement) in [javalang.tree.IfStatement]:
        return body_has_repetition(class_name, method_name, statement.then_statement) or \
               body_has_repetition(class_name, method_name, statement.else_statement)
    elif type(statement) is javalang.tree.BlockStatement:
        return body_has_repetition(class_name, method_name, statement.statements)
    elif type(statement) in [javalang.tree.WhileStatement, javalang.tree.ForStatement, javalang.tree.DoStatement]:
        return True
    elif type(statement) is javalang.tree.StatementExpression:  # recursion
        if type(statement.expression) is javalang.tree.MethodInvocation:
            if statement.expression.member == method_name:
                return True
        elif type(statement.expression) is javalang.tree.Assignment:
            if type(statement.expression.children[1]) in [javalang.tree.MemberReference, javalang.tree.ClassCreator,
                                                          javalang.tree.Literal]:
                pass
            elif type(statement.expression.children[1]) is javalang.tree.MethodInvocation:
                if statement.expression.children[1].member == method_name:
                    return True
            else:
                print("DEBUG: unknown rexp encountered in statement_has_repetition: " + str(type(statement)))
        elif type(statement.expression) is javalang.tree.MemberReference:
            pass
        else:
            print("DEBUG: unknown expression encountered in statement_has_repetition: " + str(type(statement)))
    elif type(statement) in [javalang.tree.LocalVariableDeclaration, javalang.tree.ReturnStatement,
                             javalang.tree.AssertStatement, javalang.tree.BreakStatement, javalang.tree.ContinueStatement,
                             javalang.tree.ReturnStatement, javalang.tree.ThrowStatement, javalang.tree.SynchronizedStatement,
                             javalang.tree.TryStatement, javalang.tree.SwitchStatement]:
        pass
    else:
        print("DEBUG: unknown statement encountered in statement_has_repetition: " + str(type(statement)))

    return False


def follows_constant_rule(cu, method):
    # can probably can do this on MethodDeclaration but this way prepares us for checking per class.
    for path, node_class in cu.filter(javalang.tree.ClassDeclaration):
        for node_method in node_class.methods:
            method_name = node_method.name
            if body_has_repetition(node_class.name, method_name, node_method.body) and method_name == method:
                return False

    return True


def assert_perf_constant_rules(gsr, filepaths, parse_trees, methods):
    for filename in filepaths:
        cu = parse_trees[filename]
        for method in methods:
            if not follows_constant_rule(cu, method):
                note = "{}::{} Did not meet O(1) performance requirement.".format(os.path.basename(filename), method)
                gsr.zero_by_keyword(method, note)


def follows_linear_rule(cu, method):
    # can probably can do this on MethodDeclaration but this way prepares us for checking per class.
    for path, node_class in cu.filter(javalang.tree.ClassDeclaration):
        for node_method in node_class.methods:
            method_name = node_method.name
            est = analysis_java_perf.body_est_order(node_class.name, method_name, node_method.body)
            #print("DEBUG:" + str(method_name) + " is O(" + str(est)+")")
            if est > 1 and method_name == method:
                return False

    return True


def assert_perf_linear_rules(gsr, filepaths, parse_trees, methods):
    for filename in filepaths:
        cu = parse_trees[filename]
        for method in methods:
            if not follows_linear_rule(cu, method):
                note = "{}::{} Found nested loops. Most likely does not meet O(n) performance requirement.".format(os.path.basename(filename), method)
                gsr.zero_by_keyword(method, note)


def assert_no_class_variables(gsr, filepaths, parse_trees, classes):
    for filename in filepaths:
        cu = parse_trees[filename]
        for path, node_class in cu.filter(javalang.tree.ClassDeclaration):

            if node_class.name in classes and len(node_class.fields) > 0:
                gsr.zero_all()
                note = "{}: Found class member variables.".format(node_class.name)
                gsr.add_note(note, "")
                #gsr.add_note("Disallowed packages used.", str([p[0] for p in disallowed_packages]))


if __name__ == "__main__":
    # add manually installed version of maven to path
    os.environ["PATH"] += os.pathsep + "/autograder/apache-maven-3.8.9/bin"

    with open("config.json") as file:
        config = json.load(file)

    gsr = gradescope_result.GradescopeResult()

    # verify and copy required files.
    for required in config["files_required"]:
        filepath_required = config["submission_location"] + required
        if not os.path.isfile(filepath_required):
            print("shoggoth: {} does not exist.".format(filepath_required))
            gsr.set_result_filemissing()
            gsr.save(config["filepath_results"])
            exit()
        else:
            shutil.copy(filepath_required, config["project_location"] + required)

    print("shoggoth: all required files exist.")

    # copy any optional files
    for optional in config["files_optional"]:
        filepath_optional = config["submission_location"] + optional
        if os.path.isfile(filepath_optional):
            shutil.copy(filepath_optional, config["project_location"] + optional)

    # load checkstyle setting
    enabled_checkstyle = "checkstyle_graded_rules" in config

    ret = os.system("mvn -q compile")

    # check if compilation failed
    if ret:
        gsr.set_result_buildfail()
    else:
        filepath_initial_results = "/autograder/results/results_wip.json"
        os.system("mvn -q exec:java > " + filepath_initial_results)

        if enabled_checkstyle:
            os.system("mvn checkstyle:checkstyle")  # results will be saved in target\

        # compilation succeeded, apply grading rules.
        gsr.load(filepath_initial_results)
        filepaths = [config["project_location"] + f for f in config["files_required"] + config["files_optional"]]
        filepaths = [fn for fn in filepaths if os.path.isfile(fn)]

        # build javalang parse trees for all files
        parse_trees = dict()
        for filepath in filepaths:
            with open(filepath, "r") as file:
                data = file.read()
                cu = javalang.parse.parse(data)
                parse_trees[filepath] = cu

        # evaluate checkstyle report
        if enabled_checkstyle:
            analysis_java_checkstyle.evaluate(gsr, config["checkstyle_graded_rules"])

        # 1) check for disallowed packages and zero scores if any are found.
        disallowed_packages = find_disallowed_packages(filepaths, config["package_whitelist"])
        if disallowed_packages:
            gsr.zero_all()
            gsr.add_note("Disallowed packages used.", str([p[0] for p in disallowed_packages]), True)

        # 2) assert O(1) requirement
        assert_perf_constant_rules(gsr, filepaths, parse_trees, config["assert_perf_constant"])

        # 3) assert O(n) requirement
        assert_perf_linear_rules(gsr, filepaths, parse_trees, config["assert_perf_linear"])

        # 4) assert no class variables
        assert_no_class_variables(gsr, filepaths, parse_trees, config["assert_no_class_variables"])

    gsr.save(config["filepath_results"])
