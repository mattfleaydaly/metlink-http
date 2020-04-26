import time
from sys import stderr, settrace
from threading import Lock, Event, Thread

class thread_with_trace(Thread):
  def __init__(self, *args, **keywords):
    Thread.__init__(self, *args, **keywords)
    self.killed = False

  def start(self):
    self.__run_backup = self.run
    self.run = self.__run
    Thread.start(self)

  def __run(self):
    settrace(self.globaltrace)
    self.__run_backup()
    self.run = self.__run_backup

  def globaltrace(self, frame, event, arg):
    if event == 'call':
      return self.localtrace
    else:
      return None

  def localtrace(self, frame, event, arg):
    if self.killed:
      if event == 'line':
        raise SystemExit()
    return self.localtrace

  def kill(self):
    self.killed = True

def set_timeout(target, timeout):
    def sleeper():
        if timeout > 0:
            time.sleep(timeout)
        target()

    id = thread_with_trace(target=sleeper)
    id.start()
    return id
