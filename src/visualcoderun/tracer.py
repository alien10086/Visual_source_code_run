# from __future__ import division

import inspect
import sys
import os
import time
from distutils import sysconfig
# from collections import defaultdict
from threading import Thread

from six.moves.queue import Queue, Empty

import json


# from .util import Util


class AsynchronousTracer(object):
    

    def __init__(self):
        self.processor = TraceProcessor()


    def tracer(self, frame, event, arg):
        self.processor.queue(frame, event, arg)
        return self.tracer

    def done(self):
        self.processor.done()
        self.processor.join()

    
    def start(self):
        self.processor.start()
        sys.settrace(self.tracer)

    def stop(self):
        sys.settrace(None)

    def get_output(self):

        return self.processor.output()

  


class InfoObject(object):

    def __init__(self, prev_info_ob=None, funtion_file_path="", funtion_name="", args=None, lineno=0):
        self.prev_info_ob = prev_info_ob
        self.funtion_file_path = funtion_file_path
        self.funtion_name = funtion_name
        self.args = args
        self.lineno = lineno
        self.childs = []
        self.return_value = None
        # self.start_time = None
        # self.end_time =None
        # self.call_time = None

    def __repr__(self):
        return str(self.to_dict())

    def to_dict(self):
        return {
                "funtion_file_path": self.funtion_file_path,
                "funtion_name": self.funtion_name,
                "args": self.args,
                "lineno": self.lineno,
                "childs": self.childs,
                "return_value": self.return_value
                }


    




class TraceProcessor(Thread):
    """
    使用 sys.settrace 收集函数调用信息
    """

    def __init__(self):
        Thread.__init__(self)
        self.trace_queue = Queue()
        self.keep_going = True
        self.now_info_object = None
        self.init_libpath()

    def init_libpath(self):
        self.lib_path = sysconfig.get_python_lib()
        path = os.path.split(self.lib_path)
        if path[1] == 'site-packages':
            self.lib_path = path[0]
        self.lib_path = self.lib_path.lower()

    def queue(self, frame, event, arg):
        data = {
            'frame': frame,
            'event': event,
            'arg': arg
        }
        self.trace_queue.put(data)

    def run(self):
        while self.keep_going:
            try:
                data = self.trace_queue.get(timeout=0.1)
            except Empty:
                pass
            self.process(**data)

    def done(self):
        while not self.trace_queue.empty():
            time.sleep(0.1)
        self.keep_going = False

    def push_info_ob(self, frame,full_name):
        '''
        入栈处理
        '''

        if full_name.startswith("visualcoderun."):
            return

        if self.now_info_object is None:
            info = InfoObject(
                    prev_info_ob=None, 
                    funtion_file_path=(frame.f_code.co_filename),
                    funtion_name="__main__",
                    # (module_name +"." + frame.f_code.co_name),
                    # frame.f_code.co_filename, 
                    args={},
                    lineno=0)
            self.now_info_object = info

        
        info2 = InfoObject(
                        prev_info_ob=self.now_info_object, 
                        funtion_file_path=(frame.f_code.co_filename),
                        funtion_name=full_name,
                        # (module_name +"." + frame.f_code.co_name),
                        # frame.f_code.co_filename, 
                        args=(frame.f_locals),
                        lineno=(frame.f_code.co_firstlineno))

        
        self.now_info_object.childs.append(info2)

        self.now_info_object = info2

    
    def pop_info_ob(self, full_name, arg):
        '''
        出栈处理
        '''

        if full_name.startswith("visualcoderun."):
            return

        self.now_info_object.return_value = arg
        self.now_info_object = self.now_info_object.prev_info_ob

    
    def get_full_name(self, frame):
        '''
        获取方法名绝对路径
        '''
        code = frame.f_code
        # Stores all the parts of a human readable name of the current call
        full_name_list = []
        # Work out the module name
        module = inspect.getmodule(code)

        module_name = ''
        if module:
            module_name = module.__name__
            module_path = module.__file__

            # if not self.config.include_stdlib \
            #         and self.is_module_stdlib(module_path):
            #     keep = False

            if module_name == '__main__':
                module_name = ''

        if module_name:
            full_name_list.append(module_name)

        # Work out the class name
        try:
            class_name = frame.f_locals['self'].__class__.__name__
            full_name_list.append(class_name)
        except (KeyError, AttributeError):
            pass

        # Work out the current function or method
        func_name = code.co_name
        if func_name == '?':
            func_name = '__main__'
        full_name_list.append(func_name)

        # Create a readable representation of the current call
        full_name = '.'.join(full_name_list)

        return full_name

    
   
    def process(self, frame, event, arg=None):
        """This function processes a trace result. Keeps track of
        relationships between calls.
        """

        full_name = self.get_full_name(frame)

        if event == 'call':

            self.push_info_ob(frame, full_name)

        if event == 'return':
            self.pop_info_ob(full_name, arg)

    
    def output(self):
        '''
        生成输入, 该方法线程不安全
        '''

        def serialize(obj):
            """JSON serializer for objects not serializable by default json code"""
            ret = obj.to_dict()

            def change_args(a_dict):

                if "args" in a_dict:

                    args = a_dict["args"]

                    for each_key in args.keys():

                        if not isinstance( args[each_key], (str, int, float)):
                            args[each_key] = str( args[each_key] )
                
                if a_dict["childs"]:

                    for each_child in a_dict["childs"]:
                        change_args(each_child.to_dict())

            
            change_args(ret)

            return ret

        return json.dumps(
            self.now_info_object,
            default=serialize)




def simple_memoize(callable_object):
    """Simple memoization for functions without keyword arguments.

    This is useful for mapping code objects to module in this context.
    inspect.getmodule() requires a number of system calls, which may slow down
    the tracing considerably. Caching the mapping from code objects (there is
    *one* code object for each function, regardless of how many simultaneous
    activations records there are).

    In this context we can ignore keyword arguments, but a generic memoizer
    ought to take care of that as well.
    """

    cache = dict()

    def wrapper(*rest):
        if rest not in cache:
            cache[rest] = callable_object(*rest)
        return cache[rest]

    return wrapper


inspect.getmodule = simple_memoize(inspect.getmodule)
