

# from .output import Output
# from .config import Config
from .tracer import AsynchronousTracer
# from .exceptions import PyCallGraphException


class VisualCodeRun(object):
    def __init__(self):
        """output can be a single Output instance or an iterable with many
        of them.  Example usage:
        """
        self.tracer = AsynchronousTracer()

    def __enter__(self):
        self.start()

    def __exit__(self, type, value, traceback):
        self.done()


    def start(self):
        """Begins a trace.  Setting reset to True will reset all previously
        recorded trace data.
        """
        self.tracer.start()

    def stop(self):
        """Stops the currently running trace, if any."""
        self.tracer.stop()

    def done(self):
        """Stops the trace and tells the outputters to generate their
        output.
        """
        self.stop()
        self.tracer.done()

    def generate(self):

        return self.tracer.get_output()



