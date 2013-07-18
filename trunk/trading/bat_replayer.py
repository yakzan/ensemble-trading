import os
import threading
from Tkinter import *
import tkFileDialog
import datetime
import time
import random
import glob
from batreader import *
from realtime_batreader import *
from udpsender import *
from tcpsender import *
from util import *

class Quotebook:
    def __init__(self, symbol='', bid=0, bid_volume=0, ask=0, ask_volume=0, trade=0, trade_volume=0, last_time=0):
        self.symbol, self.bid, self.bid_volume, self.ask, self.ask_volume, self.trade, self.trade_volume, self.last_time = \
            symbol, bid, bid_volume, ask, ask_volume, trade, trade_volume, last_time

    def update_with_bat(self, bat):
        (symbol, ticktype, exchange, price, size, my_time) = bat
        self.symbol = symbol
        if ticktype == 1:
            self.bid = price
            self.bid_volume = size
            self.last_time = my_time
        elif ticktype == 2:
            self.ask = price
            self.ask_volume = size
            self.last_time = my_time
        elif ticktype == 3:
            self.trade = price
            self.trade_volume = size
            self.last_time = my_time

    def to_str(self, working_date):
        secs = self.last_time
        dt_str = '%d %02d:%02d:%02d' % (working_date, secs / 3600, secs % 3600 / 60, secs % 60)
        return '%s: bid: %.4f %d, ask: %.4f %d, trade: %.4f %d, %s' % (self.symbol,
            self.bid, self.bid_volume,
            self.ask, self.ask_volume,
            self.trade, self.trade_volume, dt_str)

class BatReplayer(threading.Thread):
    def __init__(self, working_date=0, batfile='', udp_ports=[], speed=1, delay=0, market_time_zone=-4):
        self.batfile = batfile
        self.speed = speed
        self.delay = delay
        self.market_time_zone = market_time_zone
        self.udp_ports = []
        self.udp_senders = []
        self.set_udp_ports(udp_ports)
        self.working_date = working_date
        self.cur_date = working_date

        self.status = 'ready'
        self.flag_pause = 0
        self.flag_stop = 0

        self.packet_count = 0
        self.last_time = 0
        self.symbol_to_quotebook = {}
        self.last_symbol = None

        threading.Thread.__init__(self)

    def set_udp_ports(self, udp_ports):
        if not self.is_udp_ports_changed(udp_ports):
            return

        # close old senders
        if len(self.udp_senders) > 0:
            for sender in self.udp_senders:
                sender.close()
            self.udp_senders = []

        # create new senders
        self.udp_ports = udp_ports
        for udp_port in udp_ports:
            try:
                host, port = '127.0.0.1', udp_port
                if type(udp_port) is str:
                    arr = udp_port.split(':')
                    if len(arr) == 2:
                        host, port = arr[0], int(arr[1])
                    elif len(arr) == 1:
                        port = int(arr[0])

                if settings.use_tcp:
                    sender = TcpSender(host, port)
                    self.udp_senders.append(sender)
                else:
                    sender = UdpSender(host, port)
                    self.udp_senders.append(sender)
            except:
                print 'udp_port', udp_port, 'is invalid'

    def is_udp_ports_changed(self, udp_ports):
        lambda_cmp = lambda a, b: cmp(str(a), str(b))
        udp_ports.sort(lambda_cmp)
        self.udp_ports.sort(lambda_cmp)
        str_new_udp_ports = ','.join(map(str, udp_ports))
        str_old_udp_ports = ','.join(map(str, self.udp_ports))
        return str_new_udp_ports != str_old_udp_ports

    def get_symbol_quotebook(self, symbol):
        if symbol == '!':
            symbol = self.last_symbol
        if symbol == '?':
            symbols = self.symbol_to_quotebook.keys()
            if len(symbols) > 0:
                t = random.randint(0, len(symbols) - 1)
                symbol = symbols[t]
            else:
                symbol = None

        if not symbol or not self.symbol_to_quotebook.has_key(symbol):
            return ''
        else:
            symbol = symbol.upper()
            quotebook = self.symbol_to_quotebook[symbol]
            return quotebook.to_str(self.cur_date)

    def start_pause_resume_replay(self, working_date=0, batfile='', udp_ports=[], speed=1, delay=20, market_time_zone=-4):
        if self.status == 'ready' or self.batfile != batfile:
            self.start_replay(working_date, batfile, udp_ports, speed, delay, market_time_zone)
        elif self.status == 'started':
            self.pause_replay()
            self.working_date = working_date
            self.speed = speed
            self.set_udp_ports(udp_ports)
            self.delay = delay
            self.market_time_zone = market_time_zone
        elif self.status == 'paused':
            self.working_date = working_date
            self.speed = speed
            self.set_udp_ports(udp_ports)
            self.delay = delay
            self.market_time_zone = market_time_zone
            self.resume_replay()

    def start_replay(self, working_date, batfile, udp_ports, speed, delay, market_time_zone):
        self.__init__(working_date, batfile, udp_ports, speed, delay, market_time_zone)
        print working_date, batfile, udp_ports, speed, delay, market_time_zone
        self.status = 'started'
        self.start()

    def pause_replay(self):
        self.status = 'paused'
        self.flag_pause = 1

    def resume_replay(self):
        print self.working_date, self.batfile, self.udp_ports, self.speed, self.delay, self.market_time_zone
        self.status = 'started'
        self.flag_pause = 0

    def stop_replay(self):
        self.status = 'ready'
        self.flag_stop = 1

    def run(self):
        if self.batfile.find(',') > 0:
            files = self.batfile.split(',')
            dates = map(int, self.working_date.split(','))
            for f, d in zip(files, dates):
                self.play_batfile(f, d)
                time.sleep(5)
        else:
            self.play_batfile(self.batfile, self.working_date)

    def play_batfile(self, batfile, working_date):
        print repr(batfile)
        self.cur_date = working_date
        self.reader = None
        if self.delay > 0:
            self.reader = RealtimeBATReader(batfile)
            while not self.flag_stop and 0 != self.reader.init():
                time.sleep(1)
        else:
            self.reader = BATReader(batfile)
            if 0 != self.reader.init():
                print 'Failed to open BAT file.'
                self.status = 'ready'
                return

        self.status = 'started'
        self.packet_count = 0

        self.f_packets = None
        if settings.save_packets_to:
            self.f_packets = open(settings.save_packets_to, 'wb')

        if settings.send_date:
            # send DATE
            buf = 'DATE\0\0\0\0' + struct.pack('i', working_date)
            self.send_bats(buf);

        self.last_actual_time = 0
        self.data_in_last_round = 0

        while not self.flag_stop:
            if self.flag_pause:
                time.sleep(0.1)
                continue

            (data_len, buf) = self.reader.read_data()
            if data_len <= 8:
                if self.delay > 0:
                    time.sleep(1)
                    continue
                else:
                    break

            self.packet_count += 1

            self.data_in_last_round += data_len
            if 1 and self.data_in_last_round > 1024:
                time.sleep(settings.delay_per_32k / 32.0)
                self.data_in_last_round = 0

            should_send = True
            head = buf[:8].split('\0')[0]
            if head == 'MINBAR':
                for i in range(8, data_len, 36):
                    if i+36 > data_len:
                        continue
                    (symbol, HHMMSS, o, hi, lo, close, denom, volume) = \
                        unpack("8sIIIIIII", buf[i:i+36])
                    symbol = symbol.split('\0')[0]
                    my_time = HHMMSS / 10000 * 3600 + HHMMSS % 10000 / 100 * 60
                    ticktype = 3
                    exchange = '?'
                    price = float(close) / (10 ** denom)
                    bat = (symbol, ticktype, exchange, price, volume, my_time)
                    #print bat
                    self.last_symbol = symbol
                    if self.symbol_to_quotebook.has_key(symbol):
                        self.symbol_to_quotebook[symbol].update_with_bat(bat)
                    else:
                        quotebook = Quotebook()
                        quotebook.update_with_bat(bat)
                        self.symbol_to_quotebook[symbol] = quotebook

                    self.control_speed(my_time)
            elif head == 'BAT' or head == 'CNBAT':
                for i in range(8, data_len, 20): # 20: length of a BAT structure
                    if i+20 > data_len:
                        continue
                    (symbol, ticktype, exchange, price, size, my_time) = \
                        unpack("6sccfli", buf[i:i+20])
                    if head == 'BAT' and symbol.find('\0') > 0:
                        symbol = symbol.split('\0')[0]
                    elif head == 'CNBAT':
                        isymbol = unpack('i', buf[i:i+4])[0]
                        if isymbol >= 1000000 and isymbol < 2000000:
                            symbol = 'SZ%06d' % (isymbol - 1000000)
                        elif isymbol >= 0 and isymbol < 1000000:
                            symbol = 'SH%06d' % (isymbol)
                        else:
                            continue
                    ticktype = ord(ticktype)

                    self.last_symbol = symbol

                    bat = (symbol, ticktype, exchange, price, size, my_time)
                    #print head, bat
                    if self.symbol_to_quotebook.has_key(symbol):
                        self.symbol_to_quotebook[symbol].update_with_bat(bat)
                    else:
                        quotebook = Quotebook()
                        quotebook.update_with_bat(bat)
                        self.symbol_to_quotebook[symbol] = quotebook

                    self.control_speed(my_time)

                    should_send = (my_time >= 9*3600 + 28*60 and my_time <= 16*3600 + 2*60)

            # send BATs
            if should_send:
                self.send_bats(buf)


        print 'Finished reading BAT file. %d packets read.' % (self.packet_count)

        self.reader.term()

        self.status = 'ready'

        if self.f_packets:
            self.f_packets.close()

    def send_bats(self, buf):
        for sender in self.udp_senders:
            if settings.use_tcp:
                sender.send(buf) # with length header
            else:
                sender.send_rawdata(buf)

        if self.f_packets:
            self.f_packets.write(struct.pack('<i', len(buf)) + buf)
            self.f_packets.flush()

    def control_speed(self, my_time):
        if my_time > self.last_time:
            # speed control

            if self.delay == 0:

                should_full_speed = True
                if str(self.speed).lower() != 'full speed':
                    for time_from, time_to in settings.MARKET_TIMES:
                        if self.last_time >= time_from and self.last_time <= time_to and my_time >= time_from and my_time <= time_to:
                            should_full_speed = False
                            break

                if not should_full_speed:

                    process_time = time.time() - self.last_actual_time
                    sleep_time = (my_time - self.last_time) / float(self.speed) - process_time

                    #if sleep_time > 60:
                    if sleep_time > 0.5:
                        print sleep_time, my_time, self.last_time, (my_time - self.last_time)/ float(self.speed), process_time

                    try:
                        MAX_SLEEP_TIME = 2
                        while sleep_time > 0 and not self.flag_stop and not self.flag_pause:
                            if sleep_time > MAX_SLEEP_TIME:
                                time.sleep(MAX_SLEEP_TIME)
                                sleep_time -= MAX_SLEEP_TIME
                            else:
                                time.sleep(sleep_time)
                                break
                    except:
                        pass

            else:
                t = time.gmtime()
                actual_secs = (t.tm_hour + self.market_time_zone + 24) % 24 * 3600 + t.tm_min * 60 + t.tm_sec
                sleep_time = my_time + self.delay - actual_secs
                try:
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                except:
                    pass

            self.last_actual_time = time.time()
            self.last_time = my_time

class MainUI:
    def __construct(self):
        self.top = Tk()
        self.top.title('BAT Replayer')
        self.frame = Frame(self.top)
        self.frame.pack()

        self.frame_quotebook = Frame(self.frame)
        self.label_symbol = Label(self.frame_quotebook, text='Symbol', width=15)
        self.label_symbol.pack(side=LEFT)
        self.var_symbol = StringVar()
        self.var_symbol.set(settings.default_symbol)
        self.entry_symbol = Entry(self.frame_quotebook, width=10, textvariable=self.var_symbol)
        self.entry_symbol.pack(side=LEFT)
        self.label_quotebook = Label(self.frame_quotebook, text='Bid/Ask/Trade', width=70)
        self.label_quotebook.pack(side=RIGHT, fill='x')
        self.frame_quotebook.pack(side=TOP, fill='x')

        self.frame_packets = Frame(self.frame)
        self.label_packets = Label(self.frame_packets, text='Packets:', width=15)
        self.label_packets.pack(side=LEFT)
        self.label_packet_count = Label(self.frame_packets, text='0')
        self.label_packet_count.pack(side=LEFT)
        self.frame_packets.pack(side=TOP, fill='x')

        self.frame_working_date = Frame(self.frame)
        self.label_working_date = Label(self.frame_working_date, text='Working Date', width=15)
        self.label_working_date.pack(side=LEFT)
        self.var_working_date = StringVar()
        self.var_working_date.set(str(settings.working_date))
        self.entry_working_date = Entry(self.frame_working_date, width=10, textvariable=self.var_working_date)
        self.entry_working_date.pack(side=LEFT)
        self.frame_working_date.pack(side=TOP, fill='x')

        self.frame_batfile = Frame(self.frame)
        self.frame_batfile.pack(side=TOP, fill='x')
        self.label_batfile = Label(self.frame_batfile, text='BAT File', width=15)
        self.label_batfile.pack(side=LEFT, fill='x')
        self.var_batfile = StringVar()
        self.var_batfile.set(settings.batfile)
        self.entry_batfile = Entry(self.frame_batfile, width=60, textvariable=self.var_batfile)
        self.entry_batfile.pack(side=LEFT, fill='x')
        self.button_browse_batfile = Button(self.frame_batfile, text='Browse', command=self.browse_batfile)
        self.button_browse_batfile.pack(side=LEFT)

        self.frame_udp_ports = Frame(self.frame)
        self.label_udp_ports = Label(self.frame_udp_ports, text='UDP Port', width=15)
        self.label_udp_ports.pack(side=LEFT)
        self.var_udp_ports = StringVar()
        self.set_udp_ports(settings.udp_ports)
        self.entry_udp_ports = Entry(self.frame_udp_ports, width=50, textvariable=self.var_udp_ports)
        self.entry_udp_ports.pack(side=LEFT)
        self.frame_udp_ports.pack(side=TOP, fill='both')

        self.frame_speed = Frame(self.frame)
        self.label_speed = Label(self.frame_speed, text='Speed', width=15)
        self.label_speed.pack(side=LEFT)
        self.__add_speed_options()
        self.frame_speed.pack(side=TOP, fill='x')

        self.frame_delay = Frame(self.frame)
        self.label_delay = Label(self.frame_delay, text='Delay (secs)', width=15)
        self.label_delay.pack(side=LEFT)
        self.var_delay = StringVar()
        self.var_delay.set(str(settings.delay))
        self.entry_delay = Entry(self.frame_delay, width=50, textvariable=self.var_delay)
        self.entry_delay.pack(side=LEFT)
        if settings.delay > 0:
            self.frame_delay.pack(side=TOP, fill='both')

        self.frame_market_time_zone = Frame(self.frame)
        self.label_market_time_zone = Label(self.frame_market_time_zone, text='Market Time Zone', width=15)
        self.label_market_time_zone.pack(side=LEFT)
        self.var_market_time_zone = StringVar()
        self.var_market_time_zone.set(str(settings.market_time_zone))
        self.entry_market_time_zone = Entry(self.frame_market_time_zone, width=50, textvariable=self.var_market_time_zone)
        self.entry_market_time_zone.pack(side=LEFT)
        if settings.delay > 0:
            self.frame_market_time_zone.pack(side=TOP, fill='both')

        self.frame_delay_per_32k = Frame(self.frame)
        self.label_delay_per_32k = Label(self.frame_delay_per_32k, text='Delay/32K (secs)', width=15)
        self.label_delay_per_32k.pack(side=LEFT)
        self.var_delay_per_32k = StringVar()
        self.var_delay_per_32k.set(str(settings.delay_per_32k))
        self.entry_delay_per_32k = Entry(self.frame_delay_per_32k, width=50, textvariable=self.var_delay_per_32k)
        self.entry_delay_per_32k.pack(side=LEFT)
        self.frame_delay_per_32k.pack(side=TOP, fill='both')

        self.frame_control = Frame(self.frame)
        self.button_start = Button(self.frame_control, text='Start', command=self.start_pause_resume_replayer)
        self.button_start.pack(side=LEFT)
        self.button_stop = Button(self.frame_control, text='Stop', command=self.stop_replayer)
        self.button_stop.pack(side=LEFT)
        self.frame_control.pack(side=TOP)

    def __add_speed_options(self):
        self.var_speed = IntVar()
        self.speeds = [1, 2, 4, 5, 8, 10, 15, 30, 60, 'Full speed']
        self.arr_radio_speed = []
        for i, speed in enumerate(self.speeds):
            radio_speed = Radiobutton(self.frame_speed, text=str(speed), variable=self.var_speed, value=i)
            radio_speed.pack(side=LEFT)
            self.arr_radio_speed.append(radio_speed)
        self.set_replay_speed(settings.speed)

    def browse_batfile(self):
        old_dir = ''
        old_batfile = self.var_batfile.get()
        if old_batfile:
            old_dir = os.path.dirname(old_batfile)
        new_batfile = tkFileDialog.askopenfilename(defaultextension='dat', initialdir=old_dir,
            parent=self.top, title='Open BAT file')
        if new_batfile:
            self.var_batfile.set(new_batfile)
            bat_file_name = os.path.basename(new_batfile)
            try:
                date = int(bat_file_name[:8])
                self.var_working_date.set(date)
            except:
                pass

    def get_batfile(self):
        try:
            return self.var_batfile.get()
        except:
            return settings.batfile

    def get_udp_ports(self):
        str_udp_ports = self.var_udp_ports.get()
        if not str_udp_ports:
            return []

        op = lambda s: s.strip()
        return map(op, str_udp_ports.split(','))

    def set_udp_ports(self, udp_ports):
        if type(udp_ports) is list:
            self.var_udp_ports.set(','.join(map(str, udp_ports)))
        else:
            self.var_udp_ports.set(str(udp_ports))

    def get_replay_speed(self):
        return self.speeds[self.var_speed.get()]

    def set_replay_speed(self, speed):
        for i, speed_i in enumerate(self.speeds):
            if str(speed_i).lower() == str(speed).lower():
                self.var_speed.set(i)
                return

    def get_delay(self):
        try:
            return int(self.var_delay.get())
        except:
            return 20

    def get_market_time_zone(self):
        try:
            return int(self.var_market_time_zone.get())
        except:
            return 20

    def get_working_date(self):
        ret = 0
        working_date_str = self.var_working_date.get()
        if working_date_str:
            if working_date_str.find(',') > 0:
                return working_date_str
            try:
                ret = int(working_date_str)
            except:
                ret = 0

        if ret == 0:
            dt = datetime.datetime.now()
            return dt.year * 10000 + dt.month + 100 + dt.day
        else:
            return ret

    def get_delay_per_32k(self):
        try:
            return float(self.var_delay_per_32k.get())
        except:
            return 0.001

    def set_working_date(self, working_date):
        self.var_working_date.set(str(working_date))

    def start_pause_resume_replayer(self):
        settings.delay_per_32k = self.get_delay_per_32k()
        self.replayer.start_pause_resume_replay(
            self.get_working_date(), self.get_batfile(),
            self.get_udp_ports(), self.get_replay_speed(),
            self.get_delay(), self.get_market_time_zone())
        self.button_start['text'] = self.replayer.status

    def stop_replayer(self):
        self.replayer.stop_replay()
        self.button_start['text'] = 'Start'


    def run(self):
        self.__construct()

        self.replayer = BatReplayer(
            working_date=settings.working_date,
            batfile=settings.batfile,
            delay=settings.delay, market_time_zone=settings.market_time_zone)

        self.status_refresher = MainUI.StatusTimer(self, self.replayer)
        self.status_refresher.start()

        if settings.auto_start:
            self.start_pause_resume_replayer()

        self.top.mainloop()

    class StatusTimer(threading.Thread):
        def __init__(self, ui, replayer):
            self.ui = ui
            self.replayer = replayer
            threading.Thread.__init__(self)

        def run(self):
            while 1:
                time.sleep(1)
                try:
                    self.ui.label_packet_count['text'] = str(self.replayer.packet_count)
                    self.ui.label_quotebook['text'] = self.replayer.get_symbol_quotebook(self.ui.var_symbol.get())
                    if self.replayer.delay > 0:
                        t = time.gmtime()
                        print 'Market time: %02d:%02d:%02d' % (
                            (t.tm_hour + int(self.ui.var_market_time_zone.get()) + 24) % 24,
                            t.tm_min, t.tm_sec)
                    if self.replayer.status == 'ready':
                        self.ui.button_start['text'] = 'Start'
                except:
                    pass


def main():
    ui = MainUI()
    ui.run()

if __name__ == '__main__':
    import sys
    settings_file_name = 'settings.py'
    if len(sys.argv) > 1:
        settings_file_name = sys.argv[1]

    import imp
    try:
        settings = imp.load_source('settings', settings_file_name)
        print 'loaded settings from', settings_file_name
    except:
        dump_exception(0)
        import settings
        print 'loaded settings from default settings file'

    if settings.auto_set_date:
        import time
        import calendar
        t0 = time.gmtime() # UTC time
        secs0 = calendar.timegm(t0)
        secs1 = secs0 + settings.market_time_zone * 3600
        t1 = time.gmtime(secs1) # market time

        settings.working_date = t1.tm_year * 10000 + t1.tm_mon * 100 + t1.tm_mday
        settings.batfile = settings.batfile_format % settings.working_date
    else:
        try:
            files = []
            dates = []
            orig_files = glob.glob(settings.batfile_glob)
            orig_files.sort()
            for f in orig_files:
                d = int(os.path.basename(f)[:8])
                print d, f
                if d >= settings.first_date and d <= settings.last_date:
                    dates.append(d)
                    files.append(f)
            settings.batfile = ','.join(files)
            settings.working_date = ','.join(map(str, dates))
            print settings.batfile
            print settings.working_date
        except:
            dump_exception()
            pass


    main()

