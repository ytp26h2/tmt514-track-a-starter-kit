# 隨機小測資產生器：python gen.py <seed>
import random, sys
random.seed(int(sys.argv[1]))
n = random.randint(1, 8)
print(n)
print(*[random.randint(-10, 10) for _ in range(n)])
