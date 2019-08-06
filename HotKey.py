import ctypes
import ctypes.util

__all__ = ('RegisterEventHotKey', 'EventHotKeyID')

Carbon = ctypes.cdll.LoadLibrary(ctypes.util.find_library('Carbon'))

# CFTypeRef CFRetain(CFTypeRef cf);
Carbon.CFRetain.argtypes = [ctypes.c_void_p]
Carbon.CFRetain.restype = ctypes.c_void_p

# void CFRelease(CFTypeRef cf);
Carbon.CFRelease.argtypes = [ctypes.c_void_p]
Carbon.CFRelease.restype = None

# typedef struct OpaqueEventTargetRef* EventTargetRef;
#
# extern EventTargetRef
# GetApplicationEventTarget(void);
Carbon.GetApplicationEventTarget.argtypes = []
Carbon.GetApplicationEventTarget.restype = ctypes.c_void_p

# typedef UInt32 FourCharCode;
# typedef FourCharCode OSType;
#
# struct EventHotKeyID { OSType signature; UInt32 id; };
class EventHotKeyID(ctypes.Structure):
    _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

# typedef SInt32 OSStatus;
#
# extern OSStatus
# RegisterEventHotKey(
#   UInt32            inHotKeyCode,
#   UInt32            inHotKeyModifiers,
#   EventHotKeyID     inHotKeyID,
#   EventTargetRef    inTarget,
#   OptionBits        inOptions,
#   EventHotKeyRef *  outRef);
#
# extern OSStatus
# UnregisterEventHotKey(EventHotKeyRef inHotKey);

Carbon.RegisterEventHotKey.argtypes = [
	ctypes.c_uint32, ctypes.c_uint32, EventHotKeyID, ctypes.c_void_p,
    ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
Carbon.RegisterEventHotKey.restype = ctypes.c_int32
Carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
Carbon.UnregisterEventHotKey.restype = ctypes.c_int32

class EventHotKeyRef(object):
    __slots__ = ('hotKeyRef')
    def __init__(self, hotKeyRef):
        self.hotKeyRef = hotKeyRef

    @property
    def address(self):
        return self.hotKeyRef.value

    def UnregisterEventHotKey(self):
        err = Carbon.UnregisterEventHotKey(self.hotKeyRef)
        if err != 0: # noErr
            raise Exception('UnregisterEventHotKey failed: %d' % err)

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.hotKeyRef.value == other.hotKeyRef.value)

    def __hash__(self):
        return self.hotKeyRef.value

    def __repr__(self):
        return '<EventHotKeyRef: 0x%x>' % self.hotKeyRef.value

def RegisterEventHotKey(keyCode, mods, hotKeyID=EventHotKeyID(),
                        target=Carbon.GetApplicationEventTarget(), options=0):
    hotKeyRef = ctypes.c_void_p()
    err = Carbon.RegisterEventHotKey(keyCode, mods, hotKeyID,
                                     target, options, ctypes.byref(hotKeyRef))
    if err != 0: # noErr
        raise Exception('RegisterEventHotKey failed: %d' % err)
    return EventHotKeyRef(hotKeyRef)

if __name__ == '__main__':
    from Carbon.Events import cmdKey
    hk = RegisterEventHotKey(100, cmdKey)
    print hk
    hk.UnregisterEventHotKey()
