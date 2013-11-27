set timestamp=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set timestamp=%timestamp: =0%
start python trading-rt-3.py settings-fake.py 0 %timestamp%
start python trading-rt-3.py settings-fake.py 1 %timestamp%
start python trading-rt-3.py settings-fake.py 2 %timestamp%
start python trading-rt-3.py settings-fake.py 3 %timestamp%
start python trading-rt-3.py settings-fake.py 4 %timestamp%
start python trading-rt-3.py settings-fake.py 5 %timestamp%
start python trading-rt-3.py settings-fake.py 6 %timestamp%
start python trading-rt-3.py settings-fake.py 7 %timestamp%
start python trading-rt-3.py settings-fake.py 8 %timestamp%
start python trading-rt-3.py settings-fake.py 9 %timestamp%
