from ctypes import *

librv = cdll.LoadLibrary(r'c:\TIBCO\TIBRV\bin\tibrv.dll')

TIBRV_OK = 0
TIBRV_DEFAULT_QUEUE = c_int(1)
TIBRV_WAIT_FOREVER = c_double(-1.0)

tibrv_initialized = False
tibrv_queue = TIBRV_DEFAULT_QUEUE
tibrv_dispatcher = None

def tibrv_open():
    global tibrv_initialized
    global tibrv_queue
    global tibrv_dispatcher

    if not tibrv_initialized:
        status = librv.tibrv_Open()
        if status != TIBRV_OK:
            return -status

        tibrv_queue = TIBRV_DEFAULT_QUEUE

        tibrv_dispatcher = c_int()
        status = librv.tibrvDispatcher_CreateEx(
            byref(tibrv_dispatcher),
            tibrv_queue,
            TIBRV_WAIT_FOREVER)
        if status != TIBRV_OK:
            return -status

        tibrv_initialized = True

    return 0

def tibrv_close():
    global tibrv_initialized
    global tibrv_dispatcher

    if tibrv_initialized:
        librv.tibrvDispatcher_Destroy(tibrv_dispatcher)
        librv.tibrv_Close()
        tibrv_initialized = False

class TibrvTransport:
    def __init__(self, service, network, daemon):
        self.is_valid = False

        self.transport = c_int()
        status = librv.tibrvTransport_Create(
            byref(self.transport),
            c_char_p(service),
            c_char_p(network),
            c_char_p(daemon))

        self.is_valid = (status == TIBRV_OK)
        self.status = status

    def send(self, msg):
        status = librv.tibrvTransport_Send(
            self.transport,
            msg.msg)
        return status

    def set_description(self, desc):
        status = librv.tibrvTransport_SetDescription(
            self.transport,
            c_char_p(desc))
        return status

class TibrvMessage:
    def __init__(self, internal_msg=None):
        if internal_msg is None:
            self.msg = c_int()
            status = librv.tibrvMsg_Create(byref(self.msg))
            self.should_destroy = True
        else:
            self.msg = internal_msg
            self.should_destroy = False

    def destroy(self):
        if self.should_destroy and self.msg:
            librv.tibrvMsg_Destroy(self.msg)
        self.msg = 0

    def get_topic(self):
        topic = c_char_p()
        status = librv.tibrvMsg_GetSendSubject(self.msg, byref(topic))
        if status == TIBRV_OK:
            return topic.value
        else:
            return None

    def set_topic(self, topic):
        status = librv.tibrvMsg_SetSendSubject(self.msg, c_char_p(topic))

    def get_reply_topic(self):
        topic = c_char_p()
        status = librv.tibrvMsg_GetReplySubject(self.msg, byref(topic))
        if status == TIBRV_OK:
            return topic.value
        else:
            return None

    def set_reply_topic(self, topic):
        status = librv.tibrvMsg_SetReplySubject(self.msg, c_char_p(topic))

    def get_num_fields(self):
        num_fields = c_int()
        status = librv.tibrvMsg_GetNumFields(self.msg, byref(num_fields))
        if status == TIBRV_OK:
            return num_fields.value
        else:
            return 0

    def get_string(self, field, default_value=None):
        val = c_char_p()
        status = librv.tibrvMsg_GetStringEx(
            self.msg, c_char_p(field), byref(val), c_int(0))
        if status == TIBRV_OK:
            return val.value
        else:
            return default_value

    def add_string(self, field, val):
        return librv.tibrvMsg_AddStringEx(
            self.msg, c_char_p(field), c_char_p(val), c_int(0))

    def get_int(self, field, default_value=0):
        val = c_int()
        status = librv.tibrvMsg_GetI32Ex(
            self.msg, c_char_p(field), byref(val), c_int(0))
        if status == TIBRV_OK:
            return val.value
        else:
            return default_value

    def add_int(self, field, val):
        return librv.tibrvMsg_AddI32Ex(
            self.msg, c_char_p(field), c_int(val), c_int(0))

    def get_bool(self, field, default_value=False):
        val = c_int()
        status = librv.tibrvMsg_GetBoolEx(
            self.msg, c_char_p(field), byref(val), c_int(0))
        if status == TIBRV_OK:
            if val.value == 0:
                return False
            else:
                return True
        else:
            return default_value

    def add_bool(self, field, val):
        val_as_int = 1
        if not val:
            val_as_int = 0
        return librv.tibrvMsg_AddBoolEx(
            self.msg, c_char_p(field),
            c_int(valas_int), c_int(0))

    def get_float(self, field, default_value=0):
        val = c_float()
        status = librv.tibrvMsg_GetF32Ex(
            self.msg, c_char_p(field), byref(val), c_int(0))
        if status == TIBRV_OK:
            return val.value
        else:
            return default_value

    def add_float(self, field, val):
        return librv.tibrvMsg_AddF32Ex(
            self.msg, c_char_p(field), c_float(val), c_int(0))

    def add_char(self, field, val):
        return librv.tibrvMsg_AddU8Ex(
            self.msg, c_char_p(field), c_char(val), c_int(0))

    def get_bin_data(self, field):
        val = c_void_p()
        size = c_int()
        status = librv.tibrvMsg_GetOpaqueEx(
            self.msg, c_char_p(field), byref(val), byref(size), c_int(0))
        if status == TIBRV_OK:
            return val.value # FIXME
        else:
            return default_value

    def as_string(self):
        msg_as_str = c_char_p()
        status = librv.tibrvMsg_ConvertToString(self.msg, byref(msg_as_str))
        if status == TIBRV_OK:
            return msg_as_str.value
        else:
            return None

LISTENER_CALLBACK = CFUNCTYPE(None, c_int, c_int, c_void_p)

class TibrvListener(object):
    def __init__(self, transport, topic, callback):
        self.transport = transport
        self.callback = callback

        self.is_valid = False

        self.listener = c_int()
        status = librv.tibrvEvent_CreateListener(
            byref(self.listener),
            tibrv_queue,
            self.__get_callback_func(),
            self.transport.transport,
            c_char_p(topic),
            c_void_p(0))

        self.is_valid = (status == TIBRV_OK)
        self.status = status

    def destroy(self):
        librv.tibrvEvent_DestroyEx(self.listener, c_int(0))

    def __get_callback_func(self):
        def func(listener, msg, closure):
            self.on_event(listener, msg, closure)
        # Note: should hold a reference the callback
        self.__tibrv_callback = LISTENER_CALLBACK(func)
        return self.__tibrv_callback

    def on_event(self, listener, msg, closure):
        newMsg = TibrvMessage(msg)
        #print 'on_event',newMsg.as_string()
        try:
            if self.callback:
                self.callback(self.transport, newMsg)
        except 1:
            # FIXME: dump_exception
            pass
        newMsg.destroy()

if __name__ == '__main__':

    def dump_msg(transport, msg):
        print 'Received', msg.as_string()

    tibrv_open()

    trans = TibrvTransport('9094', ';238.10.10.11;', '192.168.137.1:7700')
    trans.set_description('TEST TRANS')

    listener = TibrvListener(trans, 'TEST', dump_msg)

    msg = TibrvMessage()
    msg.set_topic('TEST')
    msg.set_reply_topic('TEST.REPLY')
    msg.add_int('INT', 123456)
    msg.add_float('FLOAT', 134.1909)
    msg.add_string('STRING', 'apple')
    msg.add_char('CHAR', 'a')
    print 'SEND', msg.as_string()
    trans.send(msg)

    while True:
        cmd = raw_input('>> ')
        if cmd == 'exit':
            break

    listener.destroy()

    tibrv_close()


