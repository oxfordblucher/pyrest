from flask import Flask, abort

class Sanitation():
    def __init__(self, req):
        self.req = req
        self.req_args_dict = {}
        self.errors = []
        for k, v in self.req.args.items():
            self.req_args_dict[k] = v

    def throw_errors(self):
        if self.errors:
            return 400, ", ".join(self.errors)
            # abort(400, description=", ".join(self.errors))

            

class PageSanitizer(Sanitation):
    def check_pagination(self):
        page = ("page", 1)
        limit = ("limit", 20)

        for arg in [page, limit]:
            int_arg = None
            try:
                int_arg = int(self.req_args_dict.get(arg[0], arg[1]))
            except (ValueError, TypeError):
                self.errors.append(f"{arg[0].capitalize()} needs to be a number")

            if (int_arg and int_arg < 1):
                self.errors.append(f"{arg[0].capitalize()} needs to be greater than 0")

        
        