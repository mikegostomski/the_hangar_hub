#
#  Get information on how the code got to where it currently is
#

from base.classes.util.log import Log
from inspect import getframeinfo, stack
import os
import traceback

log = Log()


class CallerData:
    stacktrace = None
    caller = None
    calling_file_path = None  # Absolute path
    calling_file_name = None  # Basename
    calling_function = None
    calling_line = None
    steps = None

    @staticmethod
    def format_caller(caller):
        try:
            # Example: testing_views.test_status() at line 123
            # Python 3.8 does not have removesuffix()
            # filename = os.path.basename(caller.filename).removesuffix('.py')
            filename = os.path.basename(caller.filename)
            if filename.endswith(".py"):
                filename = filename[:-3]
            return f"{filename}.{caller.function}() -- line {caller.lineno}"
        except Exception as ee:
            log.error(f"Unable to format caller data: {ee}")

    def called_by(self):
        return self.format_caller(self.caller)

    def what_called(self, file_name=None, function_name=None):
        """
        Look for what called a specified point in the code execution

        Parameters:
            file_name: If looking for what called a specified file
            function_name: If looking for what called a specified function

            file_name is overloaded to also work as 'file.function'

        Example:
            CallerData().what_called(file_name="email_service")  -- What called any email_service function
            CallerData().what_called(file_name="email_service", function_name="send")  -- What called email_service.send()
            CallerData().what_called(function_name="my_function")  -- What called my_function() from any file?

            CallerData().what_called("email_service.send")  -- What called email_service.send()
        """
        # Python 3.8 does not have removesuffix()
        if file_name and file_name.endswith(".py"):
            # file_name = file_name.removesuffix('.py')
            file_name = file_name[:-3]

        # Process case where "file.function" is given as one parameter
        if file_name and "." in file_name and not function_name:
            pp = file_name.split(".")
            file_name = pp[0]
            if len(pp) > 1 and pp[1] != "py":
                function_name = pp[1]
            elif len(pp) > 2:
                function_name = pp[2]

        if function_name and function_name.endswith("()"):
            function_name = function_name[:-2]

        if not (file_name or function_name):
            log.warning("Code search must include a file or function name")
            return None

        # Search the list of steps for specified file/function
        last_step = False
        for step in self.steps:
            # Check for file match
            if not file_name:
                file_pass = True
            elif step.startswith(f"{file_name}."):
                file_pass = True
            else:
                file_pass = False

            # Check for function match
            if not function_name:
                fn_pass = True
            elif f".{function_name}()" in step:
                fn_pass = True
            else:
                fn_pass = False

            if file_pass and fn_pass:
                # This is the function that we want to return the caller for
                # (the last item in the list was the caller)
                return last_step
            else:
                last_step = step

    def __init__(self):
        """
        Get data about how the code reached this point
        """
        # Get stacktrace if this was called after an error
        try:
            self.stacktrace = traceback.format_exc(limit=10)
        except Exception as ee:
            log.warning(f"Unable to get stacktrace: {ee}")

        try:
            # Ignore this __inti__ function
            depth = 1

            # Get the info about the function that initialized this class
            caller = getframeinfo(stack()[depth][0])
            self.caller = caller
            self.calling_file_path = caller.filename
            self.calling_file_name = os.path.basename(caller.filename)
            self.calling_function = caller.function
            self.calling_line = caller.lineno

            fn_list = [self.format_caller(caller)]
            try:
                while not caller.filename.endswith("base_interceptor_middleware.py"):
                    depth += 1
                    caller = getframeinfo(stack()[depth][0])
                    # Ignore Django core function. Only interested in custom code
                    if "django/core" not in caller.filename:
                        fn_list.append(self.format_caller(caller))
            except Exception as ee:
                log.warning(f"Code depth exceeded: {depth}")

            # List in chronological order
            fn_list.reverse()
            self.steps = fn_list

        except Exception as ee:
            log.warning(f"Unable to determine calling code: {ee}")
