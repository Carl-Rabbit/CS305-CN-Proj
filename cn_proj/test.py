import threading
from queue import Queue

def worker(num):
    """thread worker function"""
    for i in range(100):
        print('Worker', num)
    return


if __name__ == '__main__':
    threads = []
    # for i in range(5):
    #     t = threading.Thread(target=worker, args=(i,))
    #     threads.append(t)
    #     t.start()
    q = Queue()
    q.put(0)
    print(q.get())
    print(q)
