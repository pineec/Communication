from src.communication import Node
import time
a = Node(port = 55566)
b = Node(port = 55588)

a.Start()
time.sleep (0.02)
b.Start()
time.sleep (0.02)
a.Send((b.host, b.port), "str", b"hello")
time.sleep (0.2)
a.kill
b.kill