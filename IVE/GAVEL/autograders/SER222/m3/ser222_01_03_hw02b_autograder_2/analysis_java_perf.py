#!/usr/bin/env python3
"""
Shoggoth - A Gradescope compatible tool for performing automatic assessment of Java homework, using static and
dynamic analysis.
"""
__author__ = "Ruben Acuna"

import javalang


def statement_estimate_order(class_name, method_name, statement):
    # see https://github.com/c2nes/javalang/blob/master/javalang/tree.py

    if type(statement) in [javalang.tree.IfStatement]:
        order = statement_estimate_order(class_name, method_name, statement.then_statement)
        if statement.else_statement:
            order_false = statement_estimate_order(class_name, method_name, statement.else_statement)
            order = max(order, order_false)
        return order
    elif type(statement) is javalang.tree.BlockStatement:
        return body_est_order(class_name, method_name, statement.statements)  #TODO: need to do above as well?
    elif type(statement) in [javalang.tree.WhileStatement, javalang.tree.ForStatement, javalang.tree.DoStatement]:
        inner_est = body_est_order(class_name, method_name, statement.body)
        return 1 + inner_est  # add order of nested loops.
    elif type(statement) is javalang.tree.StatementExpression:  # recursion
        if type(statement.expression) is javalang.tree.MethodInvocation:
            if statement.expression.member == method_name:
                return 1  # NOTE: this assumes we are making only one call to ourselves
        elif type(statement.expression) is javalang.tree.Assignment:
            if type(statement.expression.children[1]) in [javalang.tree.MemberReference, javalang.tree.ClassCreator,
                                                          javalang.tree.Literal]:
                pass
            elif type(statement.expression.children[1]) is javalang.tree.MethodInvocation:
                if statement.expression.children[1].member == method_name:
                    return 1  # NOTE: this assumes we are making only one call to ourselves
            else:
                print("DEBUG: unknown rexp encountered in statement_estimate_order: " + str(type(statement)))
        elif type(statement.expression) is javalang.tree.MemberReference:
            pass
        else:
            print("DEBUG: unknown expression encountered in statement_estimate_order: " + str(type(statement)))
    elif type(statement) in [javalang.tree.LocalVariableDeclaration, javalang.tree.ReturnStatement,
                             javalang.tree.AssertStatement, javalang.tree.BreakStatement, javalang.tree.ContinueStatement,
                             javalang.tree.ReturnStatement, javalang.tree.ThrowStatement, javalang.tree.SynchronizedStatement,
                             javalang.tree.TryStatement, javalang.tree.SwitchStatement]:
        pass
    else:
        print("DEBUG: unknown statement encountered in statement_estimate_order: " + str(type(statement)))

    return 0


def body_est_order(class_name, method_name, body):
    if not body:
        return 0  # no code is constant time
    elif type(body) is list:
        order = 0
        for statement in body:
            statement_order = statement_estimate_order(class_name, method_name, statement)
            order = max(order, statement_order)
        return order
    else:
        return statement_estimate_order(class_name, method_name, body)
